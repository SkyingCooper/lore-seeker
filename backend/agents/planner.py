"""规划 Agent：任务拆解 + 质检评分 + 个性化记忆。"""
from core.llm_router import get_llm
from agents.graph import AgentState
from langchain_core.messages import HumanMessage, SystemMessage

_PLAN_SYSTEM = """你是一个知识搜集任务的规划专家。
根据用户的查询和主题配置，输出一个 JSON 格式的搜索计划：
{
  "search_queries": ["子查询1", "子查询2", ...],
  "focus_areas": ["重点方向1", ...],
  "expected_chapters": ["章节标题1", ...]
}
只输出 JSON，不要其他内容。"""

_QC_SYSTEM = """你是一个知识文档质检专家。
评估以下 Markdown 文档的质量，输出 JSON：
{
  "score": 0-100,
  "feedback": "具体改进建议",
  "pass": true/false
}
pass=true 的标准：score >= 75，内容完整，结构清晰，无明显错误。
只输出 JSON。"""


async def planner_node(state: AgentState) -> dict:
    import json

    llm = get_llm(temperature=0.2)
    messages = [
        SystemMessage(content=_PLAN_SYSTEM),
        HumanMessage(content=f"查询：{state['query']}\n主题配置：{state['topic_config']}"),
    ]
    resp = await llm.ainvoke(messages)
    try:
        plan = json.loads(resp.content)
    except Exception:
        plan = {"search_queries": [state["query"]], "focus_areas": [], "expected_chapters": []}

    return {
        "topic_config": {**state["topic_config"], "_plan": plan},
        "iteration": state.get("iteration", 0),
    }


async def quality_check_node(state: AgentState) -> dict:
    import json

    llm = get_llm(temperature=0.1)
    messages = [
        SystemMessage(content=_QC_SYSTEM),
        HumanMessage(content=state["organized_md"][:8000]),  # 截断避免超 token
    ]
    resp = await llm.ainvoke(messages)
    try:
        result = json.loads(resp.content)
    except Exception:
        result = {"score": 60, "feedback": "解析失败，建议重试", "pass": False}

    return {
        "quality_score": result.get("score", 0),
        "quality_feedback": result.get("feedback", ""),
        "final": result.get("pass", False),
        "iteration": state.get("iteration", 0) + 1,
    }


def should_retry(state: AgentState) -> str:
    if state.get("final") or state.get("iteration", 0) >= 3:
        return "done"
    return "retry"
