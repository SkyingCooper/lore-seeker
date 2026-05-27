"""
LangGraph 多 Agent 编排图。

节点：planner → search/retrieve → organizer → planner(质检)
"""
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
import operator


class AgentState(TypedDict):
    user_id: str
    task_id: str
    query: str
    topic_config: dict                          # 主题配置（目标网站、搜索模式等）
    raw_results: Annotated[list, operator.add]  # 搜索/检索原始结果
    organized_md: str                           # 整理后的 Markdown
    toc: list                                   # 目录结构
    quality_score: float                        # 质检分数
    quality_feedback: str                       # 质检反馈
    iteration: int                              # 当前迭代次数
    final: bool                                 # 是否完成


def build_graph():
    from agents.planner import planner_node, quality_check_node, should_retry
    from agents.searcher import searcher_node
    from agents.organizer import organizer_node

    g = StateGraph(AgentState)

    g.add_node("planner", planner_node)
    g.add_node("searcher", searcher_node)
    g.add_node("organizer", organizer_node)
    g.add_node("quality_check", quality_check_node)

    g.set_entry_point("planner")
    g.add_edge("planner", "searcher")
    g.add_edge("searcher", "organizer")
    g.add_edge("organizer", "quality_check")
    g.add_conditional_edges(
        "quality_check",
        should_retry,
        {"retry": "organizer", "done": END},
    )

    return g.compile()


graph = build_graph()
