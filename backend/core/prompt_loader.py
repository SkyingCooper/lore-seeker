"""Prompt 配置加载器。

提示词统一存放在项目根目录 prompts/*.md 中。业务代码通过 prompt id 读取或渲染，
避免把大段提示词硬编码在 Agent 文件里。
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_ROOT = PROJECT_ROOT / "prompts"
PROMPT_BLOCK_RE = re.compile(
    r"<!--\s*prompt-id:\s*(?P<prompt_id>[\w.-]+)\s*-->\n(?P<body>.*?)\n<!--\s*/prompt\s*-->",
    re.DOTALL,
)


class PromptNotFoundError(KeyError):
    """Raised when a prompt id is not defined in prompts/*.md."""


@lru_cache(maxsize=1)
def load_prompts() -> dict[str, str]:
    """Load every prompt block from prompts/*.md."""

    prompts: dict[str, str] = {}
    for path in sorted(PROMPTS_ROOT.glob("*.md")):
        if path.name == "README.md":
            continue
        content = path.read_text(encoding="utf-8")
        for match in PROMPT_BLOCK_RE.finditer(content):
            prompt_id = match.group("prompt_id")
            if prompt_id in prompts:
                raise ValueError(f"Duplicate prompt id: {prompt_id}")
            prompts[prompt_id] = match.group("body").strip()
    return prompts


def get_prompt(prompt_id: str) -> str:
    """Return a raw prompt by id."""

    prompts = load_prompts()
    if prompt_id not in prompts:
        raise PromptNotFoundError(f"Prompt not found: {prompt_id}")
    return prompts[prompt_id]


def render_prompt(prompt_id: str, **variables: Any) -> str:
    """Render a prompt using string.Template variables."""

    text_variables = {key: str(value) for key, value in variables.items()}
    return Template(get_prompt(prompt_id)).substitute(text_variables)
