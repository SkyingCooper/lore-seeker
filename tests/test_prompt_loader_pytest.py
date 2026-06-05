"""Pytest coverage for prompt loading and template rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from core import prompt_loader


@pytest.fixture(autouse=True)
def clear_prompt_cache() -> None:
    prompt_loader.load_prompts.cache_clear()
    yield
    prompt_loader.load_prompts.cache_clear()


def test_render_prompt_substitutes_template_variables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "planner.md").write_text(
        "<!-- prompt-id: demo.prompt -->\nHello ${name}, query=${query}\n<!-- /prompt -->\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(prompt_loader, "PROMPTS_ROOT", tmp_path)

    rendered = prompt_loader.render_prompt("demo.prompt", name="Lore", query="asyncio")

    assert rendered == "Hello Lore, query=asyncio"


def test_get_prompt_raises_for_unknown_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_loader, "PROMPTS_ROOT", tmp_path)

    with pytest.raises(prompt_loader.PromptNotFoundError):
        prompt_loader.get_prompt("missing.prompt")


def test_load_prompts_rejects_duplicate_prompt_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "a.md").write_text(
        "<!-- prompt-id: duplicate.prompt -->\nA\n<!-- /prompt -->\n",
        encoding="utf-8",
    )
    (tmp_path / "b.md").write_text(
        "<!-- prompt-id: duplicate.prompt -->\nB\n<!-- /prompt -->\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(prompt_loader, "PROMPTS_ROOT", tmp_path)

    with pytest.raises(ValueError, match="Duplicate prompt id"):
        prompt_loader.load_prompts()
