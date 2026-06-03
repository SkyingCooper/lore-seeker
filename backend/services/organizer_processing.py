"""Organizer 预处理服务：正文抽取、可信度评分、去重、低质量分流和版本 diff。"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "source_credibility.yaml"


@dataclass(slots=True)
class ProcessedSearchResults:
    cleaned_results: list[dict[str, Any]]
    discarded_items: list[dict[str, Any]]


def process_search_results(raw_results: list[dict[str, Any]]) -> ProcessedSearchResults:
    """对搜索结果执行正文抽取、可信度排序、去重和低质量分流。"""

    cfg = _config()
    threshold = float(cfg.get("duplicate_similarity_threshold", 0.85))
    processed: list[dict[str, Any]] = []
    discarded: list[dict[str, Any]] = []

    for item in raw_results:
        normalized = dict(item)
        extracted = extract_main_content(str(item.get("content") or ""))
        normalized["content"] = extracted
        normalized["credibility_score"] = score_source(item, raw_results, cfg)
        discard_reason = classify_discard_reason(normalized, cfg)
        if discard_reason:
            normalized["discard_reason"] = discard_reason
            discarded.append(normalized)
            continue
        processed.append(normalized)

    processed.sort(key=lambda item: float(item.get("credibility_score") or 0), reverse=True)
    deduped: list[dict[str, Any]] = []
    for item in processed:
        duplicate_of = _find_duplicate(item, deduped, threshold)
        if duplicate_of is not None:
            item["discard_reason"] = "duplicate"
            item["duplicate_of"] = duplicate_of.get("url")
            discarded.append(item)
            continue
        deduped.append(item)

    return ProcessedSearchResults(cleaned_results=deduped, discarded_items=discarded)


def extract_main_content(text: str) -> str:
    """优先尝试成熟库，失败时回退到规则清洗。"""

    cleaned = text or ""
    for extractor in (_try_readability, _try_trafilatura, _try_boilerpy3):
        candidate = extractor(cleaned)
        if candidate and len(candidate.strip()) >= 100:
            return _rule_cleanup(candidate)
    return _rule_cleanup(cleaned)


def score_source(item: dict[str, Any], all_items: list[dict[str, Any]], cfg: dict[str, Any] | None = None) -> int:
    cfg = cfg or _config()
    base_scores = cfg.get("base_scores", {})
    bonuses = cfg.get("bonuses", {})
    category = _source_category(item)
    score = int(base_scores.get(category, 40))

    published_at = _parse_datetime(str(item.get("published_at") or item.get("updated_at") or ""))
    if published_at and published_at >= datetime.now(timezone.utc) - timedelta(days=30):
        score += int(bonuses.get("updated_within_30_days", 5))
    if item.get("verified_author") or item.get("author_verified"):
        score += int(bonuses.get("verified_author", 10))
    if _has_code_examples(str(item.get("content") or "")):
        score += int(bonuses.get("has_code_examples", 5))
    if _cited_by_multiple_sources(item, all_items):
        score += int(bonuses.get("cited_by_more_than_3_sources", 5))
    return score


def classify_discard_reason(item: dict[str, Any], cfg: dict[str, Any] | None = None) -> str | None:
    cfg = cfg or _config()
    allowed = set(cfg.get("discard_reasons") or [])
    content = str(item.get("content") or "").strip()
    if len(content) < 80 and "too_short" in allowed:
        return "too_short"
    if _looks_like_boilerplate(content) and "boilerplate" in allowed:
        return "boilerplate"
    if float(item.get("score") or item.get("rerank_score") or 1) < 0.15 and "low_relevance" in allowed:
        return "low_relevance"
    return None


def build_marked_html(new_text: str, old_text: str | None) -> str:
    """生成带 del/ins 标记的 HTML diff。"""

    if not old_text:
        return f'<ins class="added">{html.escape(new_text)}</ins>'

    import difflib

    matcher = difflib.SequenceMatcher(a=old_text.split(), b=new_text.split())
    parts: list[str] = []
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        old_segment = " ".join(old_text.split()[i1:i2])
        new_segment = " ".join(new_text.split()[j1:j2])
        if opcode == "equal":
            parts.append(html.escape(new_segment))
        elif opcode == "delete":
            parts.append(f"<del>{html.escape(old_segment)}</del>")
        elif opcode == "insert":
            parts.append(f'<ins class="added">{html.escape(new_segment)}</ins>')
        elif opcode == "replace":
            if old_segment:
                parts.append(f"<del>{html.escape(old_segment)}</del>")
            if new_segment:
                parts.append(f'<ins class="modified">{html.escape(new_segment)}</ins>')
    return " ".join(part for part in parts if part).strip()


def _find_duplicate(item: dict[str, Any], existing: list[dict[str, Any]], threshold: float) -> dict[str, Any] | None:
    item_tokens = _token_set(str(item.get("content") or ""))
    for other in existing:
        other_tokens = _token_set(str(other.get("content") or ""))
        similarity = _jaccard(item_tokens, other_tokens)
        if similarity >= threshold:
            return other
    return None


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[\w\u4e00-\u9fff]+", text.lower()))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


def _source_category(item: dict[str, Any]) -> str:
    domain = urlparse(str(item.get("url") or "")).netloc.lower()
    if domain.endswith(".gov") or domain.endswith(".edu") or "docs." in domain or domain.startswith("developer."):
        return "official_docs"
    if "github.com" in domain:
        return "github"
    if "stackoverflow.com" in domain or "stackexchange.com" in domain:
        return "stackoverflow"
    if any(keyword in domain for keyword in ("medium.com", "substack.com", "blog", "cnblogs.com", "juejin.cn")):
        return "technical_blog"
    return "generic_blog"


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _has_code_examples(text: str) -> bool:
    return "```" in text or bool(re.search(r"\b(def|class|function|const|let|var|SELECT|INSERT)\b", text))


def _cited_by_multiple_sources(item: dict[str, Any], all_items: list[dict[str, Any]]) -> bool:
    title = str(item.get("title") or "").strip().lower()
    if not title:
        return False
    count = 0
    for other in all_items:
        if other is item:
            continue
        other_content = str(other.get("content") or "").lower()
        if title and title[:30] in other_content:
            count += 1
    return count >= 3


def _looks_like_boilerplate(text: str) -> bool:
    lowered = text.lower()
    markers = ("copyright", "all rights reserved", "recommended reading", "导航", "免责声明", "广告", "cookie")
    return sum(marker in lowered for marker in markers) >= 2


def _rule_cleanup(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"(广告|免责声明|版权声明|推荐阅读)", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _try_readability(text: str) -> str | None:
    try:
        from readability import Document  # type: ignore
    except Exception:
        return None
    try:
        doc = Document(text)
        return doc.summary()
    except Exception:
        return None


def _try_trafilatura(text: str) -> str | None:
    try:
        import trafilatura  # type: ignore
    except Exception:
        return None
    try:
        return trafilatura.extract(text)
    except Exception:
        return None


def _try_boilerpy3(text: str) -> str | None:
    try:
        from boilerpy3 import extractors  # type: ignore
    except Exception:
        return None
    try:
        extractor = extractors.ArticleExtractor()
        return extractor.get_content(text)
    except Exception:
        return None


def _config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("source_credibility", {})
