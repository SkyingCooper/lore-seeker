from datetime import datetime
from sqlalchemy import BigInteger, ForeignKey, String, Text, DateTime, JSON, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_guest: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    topics: Mapped[list["Topic"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    search_tasks: Mapped[list["SearchTask"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    search_histories: Mapped[list["SearchHistory"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    preferences: Mapped[list["UserPreference"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    working_sessions: Mapped[list["WorkingSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    episodic_logs: Mapped[list["EpisodicLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    semantic_memories: Mapped[list["SemanticMemory"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255))
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="topics")
    search_tasks: Mapped[list["SearchTask"]] = relationship(back_populates="topic")


class SearchTask(Base):
    __tablename__ = "search_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_sites: Mapped[list] = mapped_column(JSON, default=list)
    search_mode: Mapped[str] = mapped_column(String(20), default="api")
    frequency: Mapped[str] = mapped_column(String(20), default="once")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="search_tasks")
    topic: Mapped["Topic"] = relationship(back_populates="search_tasks")
    reports: Mapped[list["Report"]] = relationship(back_populates="task")
    histories: Mapped[list["SearchHistory"]] = relationship(back_populates="task")
    working_sessions: Mapped[list["WorkingSession"]] = relationship(back_populates="task")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("search_tasks.id"))
    status: Mapped[str] = mapped_column(String(20), default="success")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execution_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    toc: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_satisfaction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    satisfaction_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["SearchTask"] = relationship(back_populates="reports")
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    histories: Mapped[list["SearchHistory"]] = relationship(back_populates="report")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reports.id"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    section_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_anchor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    report: Mapped["Report"] = relationship(back_populates="chunks")


class SearchHistory(Base):
    __tablename__ = "search_histories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("search_histories.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("search_tasks.id"))
    topic_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("topics.id"), nullable=True)
    report_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("reports.id"), nullable=True)
    query: Mapped[str] = mapped_column(Text)
    raw_results: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="search_histories")
    task: Mapped["SearchTask"] = relationship(back_populates="histories")
    topic: Mapped["Topic | None"] = relationship()
    report: Mapped["Report | None"] = relationship(back_populates="histories")


class WorkingSession(Base):
    __tablename__ = "zr_working_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    task_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("search_tasks.id"), nullable=True)
    session_key: Mapped[str] = mapped_column(String(255), unique=True)
    goal: Mapped[str] = mapped_column(Text)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    tool_cache: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="archived")
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="working_sessions")
    task: Mapped["SearchTask | None"] = relationship(back_populates="working_sessions")


class EpisodicLog(Base):
    __tablename__ = "zr_episodic_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    task_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("search_tasks.id"), nullable=True)
    session_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="episodic_logs")


class SemanticMemory(Base):
    __tablename__ = "zr_semantic_memories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User | None"] = relationship(back_populates="semantic_memories")


class UserPreference(Base):
    __tablename__ = "zr_user_preferences"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    key: Mapped[str] = mapped_column(String(255))
    value: Mapped[dict | list | str | None] = mapped_column(JSON)
    category: Mapped[str] = mapped_column(String(20), default="implicit")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="preferences")


class SkillMemory(Base):
    __tablename__ = "zr_skill_memories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str] = mapped_column(String(20), default="global")
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    trigger_patterns: Mapped[list] = mapped_column(JSON, default=list)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
