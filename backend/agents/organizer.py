"""整理 Agent：过滤、编排、生成 Markdown 知识体系 + TOC。"""
from pydantic import BaseModel, Field

from agents.graph import AgentState
from agents.contracts import validate_organizer_result
from agents.guardrails import (
    AgentErrorContext,
    AgentOutputContext,
    AgentRunContext,
    ModelRequestContext,
    after_run,
    before_model_request,
    before_run,
    build_guarded_pydantic_agent,
    on_error,
)
from agents.pydantic_runtime import build_agent_model, usage_from_pydantic_result
from core.prompt_loader import get_prompt, render_prompt
from agents.token_usage import merge_stage_usage
from core.config import settings
from services.organizer_processing import process_search_results


class OrganizerOutput(BaseModel):
    content_md: str = ""
    toc: list[dict] = Field(default_factory=list)


ORGANIZER_AGENT = build_guarded_pydantic_agent("organizer", instructions="Generate a structured markdown report.")


async def run_organizer_agent(state: AgentState) -> dict:
    operation = "generate_markdown_report"
    before_run(
        AgentRunContext(
            agent_name="organizer",
            responsibility="report_generation",
            operation=operation,
            user_id=state.get("user_id"),
            task_id=state.get("task_id"),
            state=dict(state),
        )
    )
    raw = state.get("raw_results", [])
    processed = process_search_results(raw)
    cleaned_results = processed.cleaned_results
    feedback = state.get("quality_feedback", "")

    # 截取前 20 条，避免超 token
    snippets = "\n\n".join(
        f"[{i+1}] {r.get('title','')}\n{r.get('url','')}\n{r.get('content','')[:500]}"
        for i, r in enumerate(cleaned_results[:20])
    )

    feedback_section = f"\n\n质检反馈（请改进）：{feedback}" if feedback else ""
    user_msg = render_prompt(
        "organizer.report.user",
        query=state["query"],
        snippets=snippets,
        feedback_section=feedback_section,
    )

    try:
        system_prompt = get_prompt("organizer.report.system")
        before_model_request(
            ModelRequestContext(
                agent_name="organizer",
                operation=operation,
                temperature=0.4,
                prompt_chars=len(system_prompt) + len(user_msg),
            )
        )
        resp = await ORGANIZER_AGENT.run(
            user_msg,
            output_type=OrganizerOutput,
            model=build_agent_model("organizer"),
            instructions=system_prompt,
            metadata={"agent": "organizer", "operation": operation},
        )
        token_usage = merge_stage_usage(
            state.get("token_usage"),
            stage="sort",
            usage=usage_from_pydantic_result(resp),
            model=settings.ORGANIZER_MODEL,
        )
        md = resp.output.content_md

        toc = resp.output.toc or _extract_toc(md)
        output = {
            "organized_md": md,
            "toc": toc,
            "token_usage": token_usage,
            "cleaned_raw_results": cleaned_results,
            "discarded_items": processed.discarded_items,
        }
        validate_organizer_result(state, output)
        after_run(AgentOutputContext(agent_name="organizer", operation=operation, result=output))
        return output
    except Exception as exc:
        on_error(
            AgentErrorContext(
                agent_name="organizer",
                stage="on_error",
                operation=operation,
                error_type=type(exc).__name__,
                message=str(exc),
                retryable=True,
            )
        )
        raise


async def organizer_node(state: AgentState) -> dict:
    return await run_organizer_agent(state)


def _extract_toc(md: str) -> list:
    """从 YAML front matter 或标题行提取 TOC。"""
    import re
    import yaml

    fm_match = re.match(r"^---\n(.*?)\n---", md, re.DOTALL)
    if fm_match:
        try:
            data = yaml.safe_load(fm_match.group(1))
            if isinstance(data, dict) and "toc" in data:
                return data["toc"]
        except Exception:
            pass

    # fallback：从标题行生成
    toc = []
    for line in md.splitlines():
        m = re.match(r"^(#{2,3})\s+(.+)", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            anchor = re.sub(r"[^\w一-鿿-]", "", title.lower().replace(" ", "-"))
            toc.append({"level": level, "title": title, "anchor": anchor})
    return toc
