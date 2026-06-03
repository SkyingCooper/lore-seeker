"""Agent tests.

When unittest discovery starts from ``tests/``, this package is imported as the
top-level ``agents`` package. Extend the package path so imports such as
``agents.guardrails`` still resolve to ``backend/agents``.
"""

from pathlib import Path


BACKEND_AGENTS = Path(__file__).resolve().parents[2] / "backend" / "agents"
__path__.append(str(BACKEND_AGENTS))
