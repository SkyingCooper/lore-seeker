import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    is_guest: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    topics: Mapped[list["Topic"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    search_tasks: Mapped[list["SearchTask"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    search_histories: Mapped[list["SearchHistory"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    preferences: Mapped[list["UserPreference"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    working_sessions: Mapped[list["WorkingSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    episodic_logs: Mapped[list["EpisodicLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    semantic_memories: Mapped[list["SemanticMemory"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Topic(Base):
    """用户关注的主题 + 指定搜索网站配置。"""
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_sites: Mapped[list] = mapped_column(JSON, default=list)  # ["https://..."]
    search_mode: Mapped[str] = mapped_column(String(20), default="api")  # api | crawl
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="topics")
    search_tasks: Mapped[list["SearchTask"]] = relationship(back_populates="topic")


class SearchTask(Base):
    """一次搜索任务的完整生命周期记录。"""
    __tablename__ = "search_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    query: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|done|failed
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="search_tasks")
    topic: Mapped["Topic | None"] = relationship(back_populates="search_tasks")
    report: Mapped["Report | None"] = relationship(back_populates="task", uselist=False)
    history: Mapped["SearchHistory | None"] = relationship(back_populates="task", uselist=False)
    working_sessions: Mapped[list["WorkingSession"]] = relationship(back_populates="task")


class Report(Base):
    """整理 Agent 生成的 Markdown 报告。"""
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_tasks.id"), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    content_md: Mapped[str] = mapped_column(Text)
    toc: Mapped[list] = mapped_column(JSON, default=list)  # [{level, title, anchor}]
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["SearchTask"] = relationship(back_populates="report")
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="report", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    """报告切片 + 向量，用于语义检索。"""
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    report: Mapped["Report"] = relationship(back_populates="chunks")


class SearchHistory(Base):
    """用户搜索历史：每次搜索产生一条，记录知识库版本入口和 Agent 工作记忆关联。

    version：同一 topic 下第 n 次搜索（无 topic 时按 query 分组），由 service 层写入时计算。
    report_title / report_summary：任务完成后由 worker 回填，供列表页快速展示，无需 JOIN。
    """
    __tablename__ = "search_histories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_tasks.id"), unique=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reports.id"), nullable=True)  # 任务完成后填入
    query: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="search_histories")
    task: Mapped["SearchTask"] = relationship(back_populates="history")
    topic: Mapped["Topic | None"] = relationship()
    report: Mapped["Report | None"] = relationship()


# ─── Agent 五类记忆表 ────────────────────────────────────────────────────────


class WorkingSession(Base):
    """工作记忆归档表。

    活跃状态存于 Redis（key: working_session:{session_key}），
    会话结束后异步写入此表，Redis 中删除。
    """
    __tablename__ = "working_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("search_tasks.id"), nullable=True)  # 关联本次搜索
    session_key: Mapped[str] = mapped_column(String(255), unique=True)  # Redis key
    goal: Mapped[str] = mapped_column(Text)                             # 当前目标
    current_step: Mapped[int] = mapped_column(Integer, default=0)       # 执行到第几步
    steps: Mapped[list] = mapped_column(JSON, default=list)             # 步骤执行记录
    tool_cache: Mapped[dict] = mapped_column(JSON, default=dict)        # 工具调用结果缓存
    status: Mapped[str] = mapped_column(String(20), default="archived") # active | archived
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="working_sessions")
    task: Mapped["SearchTask | None"] = relationship(back_populates="working_sessions")


class EpisodicLog(Base):
    """情景记忆：系统流水账日记。

    记录每次完整的对话记录、任务执行日志等"发生了什么"。
    """
    __tablename__ = "episodic_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("search_tasks.id"), nullable=True)
    session_key: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 关联工作记忆
    event_type: Mapped[str] = mapped_column(String(50))  # conversation | task_run | search | error
    content: Mapped[str] = mapped_column(Text)           # 完整对话记录或任务执行日志
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="episodic_logs")


class SemanticMemory(Base):
    """语义记忆：知识规律 + 向量检索。

    存储从对话和任务中提炼的知识/规律，embedding 基于 summary 计算。
    """
    __tablename__ = "semantic_memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # null=全局
    title: Mapped[str] = mapped_column(String(500))   # 一句话概括
    summary: Mapped[str] = mapped_column(Text)        # 精简摘要（用于快速预览）
    content: Mapped[str] = mapped_column(Text)        # 完整内容
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))  # summary 的向量
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)   # report | conversation | manual
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User | None"] = relationship(back_populates="semantic_memories")


class UserPreference(Base):
    """用户偏好记忆：显式/隐式配置，key-value 形式。"""
    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    key: Mapped[str] = mapped_column(String(255))
    value: Mapped[dict | list | str | None] = mapped_column(JSON)
    category: Mapped[str] = mapped_column(String(20), default="implicit")  # explicit | implicit
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 隐式偏好的置信度
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="preferences")


class SkillMemory(Base):
    """Skill 记忆：操作 SOP，三层结构按需加载。

    title   — 一级，关键词/标题，用于快速匹配和索引
    content — 二级，完整 SOP 步骤内容
    citation — 三级，引用与解释（来源说明、边界条件、例外情况）
    """
    __tablename__ = "skill_memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255))       # 一级：关键词/标题
    content: Mapped[str] = mapped_column(Text)            # 二级：完整 SOP 内容
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)  # 三级：引用与解释
    scope: Mapped[str] = mapped_column(String(20), default="global")   # global | user
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    trigger_patterns: Mapped[list] = mapped_column(JSON, default=list)  # 触发匹配关键词列表
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
