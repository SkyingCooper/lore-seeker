"""上下文管理服务：按场景注入、裁剪、摘要和压缩 prompt 上下文。

该模块只做本地确定性处理，不调用模型；模型级 token 计数不可用时使用
字符数 / 4 的保守估算，保证 Agent、Tool、DB/Redis 交互都有统一上下文入口。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SkillMemory, UserPreference

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "context_manager.yaml"

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5}


@dataclass(slots=True)
class ContextItem:
    priority: str
    name: str
    content: str
    can_trim: bool = True
    can_summarize: bool = True


def build_context(items: Iterable[ContextItem], *, scenario: str = "agent_communication") -> dict[str, Any]:
    """按 P0 -> P5 组织上下文，超阈值时从低优先级开始裁剪。"""

    cfg = _scenario_config(scenario)
    max_tokens = int(cfg.get("max_tokens") or _config()["default_max_tokens"])
    threshold = float(cfg.get("trim_threshold") or _config()["trim_threshold"])
    budget = int(max_tokens * threshold)

    ordered = sorted(items, key=lambda item: PRIORITY_ORDER.get(item.priority, 9))
    kept = list(ordered)
    actions: list[dict[str, Any]] = []

    while _count_items(kept) > budget:
        target_index = _find_lowest_trim_candidate(kept)
        if target_index is None:
            break
        target = kept[target_index]
        if target.can_summarize and len(target.content) > 400:
            summarized = textrank_summary(target.content)
            actions.append({"action": "summarize", "item": target.name, "from": len(target.content), "to": len(summarized)})
            kept[target_index] = ContextItem(target.priority, target.name, summarized, target.can_trim, False)
        else:
            actions.append({"action": "drop", "item": target.name, "priority": target.priority})
            kept.pop(target_index)

        if not kept:
            break

    if _count_items(kept) > max_tokens:
        compressed = _rule_compress(_render_items(kept), target_ratio=float(_config()["compressor"].get("target_ratio", 0.15)))
        return {
            "context": compressed,
            "items": [],
            "token_estimate": estimate_tokens(compressed),
            "actions": actions + [{"action": "compress", "method": "rule_based"}],
            "truncated": True,
        }

    rendered = _render_items(kept)
    return {
        "context": rendered,
        "items": [asdict(item) for item in kept],
        "token_estimate": estimate_tokens(rendered),
        "actions": actions,
        "truncated": bool(actions),
    }


async def load_task_start_context(db: AsyncSession, *, user_id: int) -> dict[str, Any]:
    """新任务开始前加载第一阶段 Skill 和用户偏好。"""

    prefs = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    skills = await db.execute(
        select(SkillMemory)
        .where(
            SkillMemory.status == "active",
            (SkillMemory.scope == "global") | (SkillMemory.user_id == user_id),
        )
        .order_by(SkillMemory.confidence.desc(), SkillMemory.last_used_at.desc().nullslast())
        .limit(50)
    )
    items = [
        ContextItem(
            priority="P3",
            name="user_preferences",
            content="\n".join(f"- {pref.key}: {pref.value}" for pref in prefs.scalars()),
        ),
        ContextItem(
            priority="P3",
            name="skill_stage_one",
            content="\n".join(
                f"- #{skill.id} {skill.title}: {skill.desc or ''}" for skill in skills.scalars()
            ),
        ),
    ]
    return build_context(items, scenario="task_start_initial_load")


def textrank_summary(text: str) -> str:
    """本地摘要：用词频近似 TextRank，保留得分最高的句子。"""

    cfg = _config()["summarizer"]
    sentences = _split_sentences(text)
    if len(sentences) <= int(cfg.get("min_sentences", 2)):
        return text.strip()

    words = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    freq: dict[str, int] = {}
    for word in words:
        if len(word) <= 1:
            continue
        freq[word] = freq.get(word, 0) + 1

    scored = []
    for index, sentence in enumerate(sentences):
        score = sum(freq.get(word, 0) for word in re.findall(r"[\w\u4e00-\u9fff]+", sentence.lower()))
        scored.append((score, index, sentence))

    max_sentences = int(cfg.get("max_sentences", 5))
    target_count = max(int(len(sentences) * float(cfg.get("target_ratio", 0.3))), int(cfg.get("min_sentences", 2)))
    selected = sorted(scored, reverse=True)[: min(max_sentences, target_count)]
    return "".join(sentence for _, _, sentence in sorted(selected, key=lambda item: item[1])).strip()


def estimate_tokens(text: str) -> int:
    """没有 provider tokenizer 时的保守估算。"""

    return max(1, len(text) // 4)


def _config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {
            "default_max_tokens": 8192,
            "trim_threshold": 0.8,
            "scenarios": {},
            "summarizer": {"target_ratio": 0.3, "min_sentences": 2, "max_sentences": 5},
            "compressor": {"target_ratio": 0.15},
        }
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("context_manager", {})


def _scenario_config(scenario: str) -> dict[str, Any]:
    cfg = _config()
    return (cfg.get("scenarios") or {}).get(scenario, {})


def _render_items(items: list[ContextItem]) -> str:
    return "\n\n".join(f"## {item.name}\n{item.content}" for item in items if item.content.strip())


def _count_items(items: list[ContextItem]) -> int:
    return sum(estimate_tokens(item.content) for item in items)


def _find_lowest_trim_candidate(items: list[ContextItem]) -> int | None:
    for priority in ("P5", "P4", "P3", "P2"):
        for index in range(len(items) - 1, -1, -1):
            item = items[index]
            if item.priority == priority and item.can_trim:
                return index
    return None


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？.!?])\s+", text.strip())
    return [part for part in parts if part]


def _rule_compress(text: str, *, target_ratio: float) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    keep = max(1, int(len(lines) * target_ratio))
    return "\n".join(lines[:keep])
