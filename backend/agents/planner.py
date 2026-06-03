"""规划 Agent：任务拆解 + 质检评分 + 个性化记忆。"""
from pydantic import BaseModel, Field

from core.prompt_loader import get_prompt, render_prompt
from agents.graph import AgentState
from agents.contracts import validate_planner_to_searcher_task, validate_quality_result
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
from agents.token_usage import merge_stage_usage
from core.config import settings


class PlannerPlanOutput(BaseModel):
    search_queries: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    expected_chapters: list[str] = Field(default_factory=list)
    intent_summary: str = ""
    needs_query_optimization: bool = False
    needs_decomposition: bool = False
    planner_notes: str | None = None


class PlannerQualityOutput(BaseModel):
    score: int = 60
    feedback: str = "解析失败，建议重试"
    pass_: bool = Field(default=False, alias="pass")


PLANNER_PLAN_AGENT = build_guarded_pydantic_agent("planner", instructions="Generate a structured search plan.")
PLANNER_QUALITY_AGENT = build_guarded_pydantic_agent("planner", instructions="Evaluate organizer output quality.")


async def run_planner_agent(state: AgentState) -> dict:

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
        resp = await PLANNER_PLAN_AGENT.run(
            user_content,
            output_type=PlannerPlanOutput,
            model=build_agent_model("planner"),
            instructions=system_prompt,
            metadata={"agent": "planner", "operation": operation},
        )
        token_usage = merge_stage_usage(
            state.get("token_usage"),
            stage="planner",
            usage=usage_from_pydantic_result(resp),
            model=settings.PLANNER_MODEL,
        )
        plan = resp.output.model_dump(by_alias=True)
        if not plan.get("search_queries"):
            plan["search_queries"] = [state["query"]]

        validate_planner_to_searcher_task(state, plan)
        result = {
            "topic_config": {**state["topic_config"], "_plan": plan},
            "token_usage": token_usage,
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


async def run_quality_check_agent(state: AgentState) -> dict:

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
        resp = await PLANNER_QUALITY_AGENT.run(
            user_content,
            output_type=PlannerQualityOutput,
            model=build_agent_model("planner"),
            instructions=system_prompt,
            metadata={"agent": "planner", "operation": operation},
        )
        token_usage = merge_stage_usage(
            state.get("token_usage"),
            stage="planner",
            usage=usage_from_pydantic_result(resp),
            model=settings.PLANNER_MODEL,
        )
        result = resp.output.model_dump(by_alias=True)

        output = {
            "quality_score": result.get("score", 0),
            "quality_feedback": result.get("feedback", ""),
            "final": result.get("pass", False),
            "token_usage": token_usage,
            "iteration": state.get("iteration", 0) + 1,
        }
        validate_quality_result(state, output)
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


async def planner_node(state: AgentState) -> dict:
    return await run_planner_agent(state)


async def quality_check_node(state: AgentState) -> dict:
    return await run_quality_check_agent(state)


def should_retry(state: AgentState) -> str:
    if state.get("final") or state.get("iteration", 0) >= 3:
        return "done"
    return "retry"
