"""整理 Agent：过滤、编排、生成 Markdown 知识体系 + TOC。"""
from agents.graph import AgentState
from agents.guardrails import (
    AgentErrorContext,
    AgentOutputContext,
    AgentRunContext,
    ModelRequestContext,
    after_run,
    before_model_request,
    before_run,
    on_error,
)
from core.llm_router import get_llm
from core.prompt_loader import get_prompt, render_prompt
from langchain_core.messages import HumanMessage, SystemMessage
from agents.token_usage import merge_stage_usage, usage_from_response
from core.config import settings


async def organizer_node(state: AgentState) -> dict:
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
    feedback = state.get("quality_feedback", "")

    # 截取前 20 条，避免超 token
    snippets = "\n\n".join(
        f"[{i+1}] {r.get('title','')}\n{r.get('url','')}\n{r.get('content','')[:500]}"
        for i, r in enumerate(raw[:20])
    )

    feedback_section = f"\n\n质检反馈（请改进）：{feedback}" if feedback else ""
    user_msg = render_prompt(
        "organizer.report.user",
        query=state["query"],
        snippets=snippets,
        feedback_section=feedback_section,
    )

    try:
        llm = get_llm(temperature=0.4)
        system_prompt = get_prompt("organizer.report.system")
        before_model_request(
            ModelRequestContext(
                agent_name="organizer",
                operation=operation,
                temperature=0.4,
                prompt_chars=len(system_prompt) + len(user_msg),
            )
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg),
        ]
        resp = await llm.ainvoke(messages)
        token_usage = merge_stage_usage(
            state.get("token_usage"),
            stage="sort",
            usage=usage_from_response(resp),
            model=settings.ORGANIZER_MODEL,
        )
        md = resp.content

        toc = _extract_toc(md)
        output = {"organized_md": md, "toc": toc, "token_usage": token_usage}
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
