"""规划 Agent：任务拆解 + 质检评分 + 个性化记忆。"""
from core.llm_router import get_llm
from core.prompt_loader import get_prompt, render_prompt
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
from langchain_core.messages import HumanMessage, SystemMessage


async def planner_node(state: AgentState) -> dict:
    import json

    operation = "decompose_task"
    before_run(
        AgentRunContext(
            agent_name="planner",
            responsibility="task_planning",
            operation=operation,
            user_id=state.get("user_id"),
            task_id=state.get("task_id"),
            state=dict(state),
        )
    )
    try:
        llm = get_llm(temperature=0.2)
        system_prompt = get_prompt("planner.plan.system")
        user_content = render_prompt(
            "planner.plan.user",
            query=state["query"],
            topic_config=state["topic_config"],
        )
        before_model_request(
            ModelRequestContext(
                agent_name="planner",
                operation=operation,
                temperature=0.2,
                prompt_chars=len(system_prompt) + len(user_content),
            )
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
        resp = await llm.ainvoke(messages)
        try:
            plan = json.loads(resp.content)
        except Exception:
            plan = {"search_queries": [state["query"]], "focus_areas": [], "expected_chapters": []}

        result = {
            "topic_config": {**state["topic_config"], "_plan": plan},
            "iteration": state.get("iteration", 0),
        }
        after_run(AgentOutputContext(agent_name="planner", operation=operation, result=result))
        return result
    except Exception:
        on_error(
            AgentErrorContext(
                agent_name="planner",
                stage="on_error",
                operation=operation,
                error_type="planner_node_error",
                message="Planner failed to generate a structured plan.",
                retryable=True,
            )
        )
        raise


async def quality_check_node(state: AgentState) -> dict:
    import json

    operation = "evaluate_organizer_result"
    before_run(
        AgentRunContext(
            agent_name="planner",
            responsibility="organizer_quality_check",
            operation=operation,
            user_id=state.get("user_id"),
            task_id=state.get("task_id"),
            state=dict(state),
        )
    )
    try:
        llm = get_llm(temperature=0.1)
        content = state["organized_md"][:8000]  # 截断避免超 token
        system_prompt = get_prompt("planner.quality_check.system")
        user_content = render_prompt("planner.quality_check.user", organized_md=content)
        before_model_request(
            ModelRequestContext(
                agent_name="planner",
                operation=operation,
                temperature=0.1,
                prompt_chars=len(system_prompt) + len(user_content),
            )
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
        resp = await llm.ainvoke(messages)
        try:
            result = json.loads(resp.content)
        except Exception:
            result = {"score": 60, "feedback": "解析失败，建议重试", "pass": False}

        output = {
            "quality_score": result.get("score", 0),
            "quality_feedback": result.get("feedback", ""),
            "final": result.get("pass", False),
            "iteration": state.get("iteration", 0) + 1,
        }
        after_run(AgentOutputContext(agent_name="planner", operation=operation, result=output))
        return output
    except Exception:
        on_error(
            AgentErrorContext(
                agent_name="planner",
                stage="on_error",
                operation=operation,
                error_type="quality_check_error",
                message="Planner failed to evaluate organizer output.",
                retryable=True,
            )
        )
        raise


def should_retry(state: AgentState) -> str:
    if state.get("final") or state.get("iteration", 0) >= 3:
        return "done"
    return "retry"
