-- =============================================================================
-- Lore Seeker · PostgreSQL Schema
-- =============================================================================
-- 执行方式：psql -U <user> -d <db> -f schema.sql
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- 触发器函数：自动维护 updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 业务核心表
-- =============================================================================

CREATE TABLE users (
    id              UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE,
    hashed_password VARCHAR(255),
    fingerprint     VARCHAR(255) UNIQUE,
    is_guest        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  users                 IS '用户表，支持邮箱注册用户与浏览器指纹游客两种身份';
COMMENT ON COLUMN users.id              IS '用户主键，UUID';
COMMENT ON COLUMN users.email           IS '注册用户邮箱，游客为 NULL';
COMMENT ON COLUMN users.hashed_password IS 'bcrypt 哈希密码，游客为 NULL';
COMMENT ON COLUMN users.fingerprint     IS '浏览器指纹，游客身份唯一标识，注册用户为 NULL';
COMMENT ON COLUMN users.is_guest        IS '是否游客；TRUE = 仅凭指纹登录，FALSE = 邮箱注册用户';
COMMENT ON COLUMN users.created_at      IS '账号创建时间';

-- -----------------------------------------------------------------------------

CREATE TABLE topics (
    id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name         VARCHAR(255) NOT NULL,
    description  TEXT,
    target_sites JSONB        NOT NULL DEFAULT '[]',
    search_mode  VARCHAR(20)  NOT NULL DEFAULT 'api',
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  topics             IS '用户自定义的搜索主题，包含目标网站和搜索模式配置';
COMMENT ON COLUMN topics.id          IS '主题主键，UUID';
COMMENT ON COLUMN topics.user_id     IS '所属用户，级联删除';
COMMENT ON COLUMN topics.name        IS '主题名称，如"LangGraph 最佳实践"';
COMMENT ON COLUMN topics.description IS '主题描述，可为空';
COMMENT ON COLUMN topics.target_sites IS '指定搜索的目标网站列表，格式 ["https://..."]；空数组表示不限定';
COMMENT ON COLUMN topics.search_mode  IS '搜索模式：api（调用搜索 API）| crawl（Playwright 爬虫）';
COMMENT ON COLUMN topics.created_at   IS '主题创建时间';

-- -----------------------------------------------------------------------------

CREATE TABLE search_tasks (
    id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic_id      UUID        REFERENCES topics(id) ON DELETE SET NULL,
    query         TEXT        NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'pending',
    quality_score FLOAT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at   TIMESTAMPTZ
);
COMMENT ON TABLE  search_tasks               IS '一次搜索任务的完整生命周期记录，状态机驱动 Agent 流水线';
COMMENT ON COLUMN search_tasks.id            IS '任务主键，UUID';
COMMENT ON COLUMN search_tasks.user_id       IS '发起搜索的用户，级联删除';
COMMENT ON COLUMN search_tasks.topic_id      IS '关联主题，主题删除后置 NULL，任务保留';
COMMENT ON COLUMN search_tasks.query         IS '用户原始查询文本';
COMMENT ON COLUMN search_tasks.status        IS '任务状态：pending | running | done | failed';
COMMENT ON COLUMN search_tasks.quality_score IS '规划 Agent 对最终报告的质检评分（0~100），未完成时为 NULL';
COMMENT ON COLUMN search_tasks.created_at    IS '任务创建时间';
COMMENT ON COLUMN search_tasks.finished_at   IS '任务完成或失败时间，未结束时为 NULL';

-- -----------------------------------------------------------------------------

CREATE TABLE reports (
    id         UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id    UUID         NOT NULL UNIQUE REFERENCES search_tasks(id) ON DELETE CASCADE,
    title      VARCHAR(500) NOT NULL,
    content_md TEXT         NOT NULL,
    toc        JSONB        NOT NULL DEFAULT '[]',
    summary    TEXT,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  reports            IS '整理 Agent 输出的 Markdown 知识文档，每个任务唯一对应一份';
COMMENT ON COLUMN reports.id         IS '报告主键，UUID';
COMMENT ON COLUMN reports.task_id    IS '关联搜索任务，唯一约束保证一任务一报告，级联删除';
COMMENT ON COLUMN reports.title      IS '报告标题，由整理 Agent 生成';
COMMENT ON COLUMN reports.content_md IS '完整 Markdown 正文';
COMMENT ON COLUMN reports.toc        IS '目录结构，格式 [{level, title, anchor}]，由整理 Agent 提取';
COMMENT ON COLUMN reports.summary    IS '报告摘要，用于快速预览，可为空';
COMMENT ON COLUMN reports.created_at IS '报告生成时间';

-- -----------------------------------------------------------------------------

CREATE TABLE knowledge_chunks (
    id          UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id   UUID         NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    chunk_index INTEGER      NOT NULL,
    content     TEXT         NOT NULL,
    embedding   vector(1536) NOT NULL,
    metadata    JSONB        NOT NULL DEFAULT '{}'
);
COMMENT ON TABLE  knowledge_chunks             IS '报告按标题分段切片后的向量化存储，用于语义相似度检索';
COMMENT ON COLUMN knowledge_chunks.id          IS '切片主键，UUID';
COMMENT ON COLUMN knowledge_chunks.report_id   IS '所属报告，级联删除';
COMMENT ON COLUMN knowledge_chunks.chunk_index IS '切片在报告中的顺序序号，从 0 开始';
COMMENT ON COLUMN knowledge_chunks.content     IS '切片文本内容';
COMMENT ON COLUMN knowledge_chunks.embedding   IS '切片内容的向量表示，维度 1536（DashScope text-embedding-v3 / OpenAI text-embedding-3-small）';
COMMENT ON COLUMN knowledge_chunks.metadata    IS '扩展元数据，如来源章节标题、URL 等';

-- =============================================================================
-- 搜索历史表
-- =============================================================================

CREATE TABLE search_histories (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id    UUID        NOT NULL UNIQUE REFERENCES search_tasks(id) ON DELETE CASCADE,
    topic_id   UUID        REFERENCES topics(id) ON DELETE SET NULL,
    report_id  UUID        REFERENCES reports(id) ON DELETE SET NULL,
    query      TEXT        NOT NULL,
    version    INTEGER     NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  search_histories            IS '用户搜索历史，记录第几次搜索及关联的知识文档入口';
COMMENT ON COLUMN search_histories.id         IS '历史记录主键，UUID';
COMMENT ON COLUMN search_histories.user_id    IS '所属用户，级联删除';
COMMENT ON COLUMN search_histories.task_id    IS '关联搜索任务，唯一约束保证一任务一条历史，级联删除';
COMMENT ON COLUMN search_histories.topic_id   IS '冗余存储关联主题，加速按主题过滤；主题删除后置 NULL';
COMMENT ON COLUMN search_histories.report_id  IS '关联知识文档（reports），任务完成后由 worker 回填；通过 report → knowledge_chunks 获取本次搜索产出的所有切片；报告删除后置 NULL';
COMMENT ON COLUMN search_histories.query      IS '冗余存储原始查询文本，历史列表页免 JOIN';
COMMENT ON COLUMN search_histories.version    IS '同一 topic（或同一 query）下第 n 次搜索，由 service 层写入时计算';
COMMENT ON COLUMN search_histories.created_at IS '历史记录创建时间，等同于任务触发时间';

-- =============================================================================
-- Agent 五类记忆表
-- =============================================================================

CREATE TABLE working_sessions (
    id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id      UUID         REFERENCES search_tasks(id) ON DELETE SET NULL,
    session_key  VARCHAR(255) NOT NULL UNIQUE,
    goal         TEXT         NOT NULL,
    current_step INTEGER      NOT NULL DEFAULT 0,
    steps        JSONB        NOT NULL DEFAULT '[]',
    tool_cache   JSONB        NOT NULL DEFAULT '{}',
    status       VARCHAR(20)  NOT NULL DEFAULT 'archived',
    started_at   TIMESTAMPTZ  NOT NULL,
    ended_at     TIMESTAMPTZ
);
COMMENT ON TABLE  working_sessions              IS 'Agent 工作记忆归档表；活跃态存于 Redis，会话结束后异步写入并删除 Redis key';
COMMENT ON COLUMN working_sessions.id           IS '工作记忆归档主键，UUID';
COMMENT ON COLUMN working_sessions.user_id      IS '所属用户，级联删除';
COMMENT ON COLUMN working_sessions.task_id      IS '关联触发本次工作记忆的搜索任务；任务删除后置 NULL，归档记录保留';
COMMENT ON COLUMN working_sessions.session_key  IS 'Redis key（working_session:{session_key}），活跃会话的唯一标识';
COMMENT ON COLUMN working_sessions.goal         IS '本次会话的当前目标描述';
COMMENT ON COLUMN working_sessions.current_step IS 'Agent 执行到第几步，归档时记录最终步骤数';
COMMENT ON COLUMN working_sessions.steps        IS '步骤执行记录列表，格式 [{step, action, result, timestamp}]';
COMMENT ON COLUMN working_sessions.tool_cache   IS '工具调用结果缓存，格式 {tool_name: result}';
COMMENT ON COLUMN working_sessions.status       IS '会话状态：active（Redis 中活跃）| archived（已归档到 DB）';
COMMENT ON COLUMN working_sessions.started_at   IS '会话开始时间';
COMMENT ON COLUMN working_sessions.ended_at     IS '会话结束时间，active 状态时为 NULL';

-- -----------------------------------------------------------------------------

CREATE TABLE episodic_logs (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id     UUID        REFERENCES search_tasks(id) ON DELETE SET NULL,
    session_key VARCHAR(255),
    event_type  VARCHAR(50) NOT NULL,
    content     TEXT        NOT NULL,
    metadata    JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  episodic_logs             IS '情景记忆：系统流水账日记，按事件类型记录每次对话和任务执行过程';
COMMENT ON COLUMN episodic_logs.id          IS '情景日志主键，UUID';
COMMENT ON COLUMN episodic_logs.user_id     IS '所属用户，级联删除';
COMMENT ON COLUMN episodic_logs.task_id     IS '关联搜索任务，可为空（非任务驱动的对话也会记录）；任务删除后置 NULL';
COMMENT ON COLUMN episodic_logs.session_key IS '关联工作记忆的 session_key，可通过此字段与 working_sessions 关联';
COMMENT ON COLUMN episodic_logs.event_type  IS '事件类型：conversation（对话）| task_run（任务执行）| search（搜索动作）| error（异常）';
COMMENT ON COLUMN episodic_logs.content     IS '事件完整内容，如完整对话记录、任务执行日志';
COMMENT ON COLUMN episodic_logs.metadata    IS '扩展上下文，如 token 消耗、耗时、模型版本等';
COMMENT ON COLUMN episodic_logs.created_at  IS '事件发生时间';

-- -----------------------------------------------------------------------------

CREATE TABLE semantic_memories (
    id          UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID         REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(500) NOT NULL,
    summary     TEXT         NOT NULL,
    content     TEXT         NOT NULL,
    embedding   vector(1536) NOT NULL,
    source_type VARCHAR(50),
    source_id   UUID,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  semantic_memories             IS '语义记忆：从对话和任务中提炼的知识规律，embedding 基于 summary 计算，支持向量检索';
COMMENT ON COLUMN semantic_memories.id          IS '语义记忆主键，UUID';
COMMENT ON COLUMN semantic_memories.user_id     IS '所属用户；NULL 表示全局记忆，对所有用户可见；用户删除后级联删除';
COMMENT ON COLUMN semantic_memories.title       IS '一句话概括，用于快速索引和展示';
COMMENT ON COLUMN semantic_memories.summary     IS '精简摘要，用于快速预览；embedding 基于此字段计算';
COMMENT ON COLUMN semantic_memories.content     IS '完整内容，向量检索命中后按需加载';
COMMENT ON COLUMN semantic_memories.embedding   IS 'summary 的向量表示，维度 1536；用于语义相似度检索';
COMMENT ON COLUMN semantic_memories.source_type IS '知识来源类型：report（来自报告）| conversation（来自对话）| manual（手动录入）';
COMMENT ON COLUMN semantic_memories.source_id   IS '来源记录的 UUID，与 source_type 配合使用，可为空';
COMMENT ON COLUMN semantic_memories.created_at  IS '记忆创建时间';

-- -----------------------------------------------------------------------------

CREATE TABLE user_preferences (
    id         UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key        VARCHAR(255) NOT NULL,
    value      JSONB,
    category   VARCHAR(20)  NOT NULL DEFAULT 'implicit',
    confidence FLOAT,
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  user_preferences            IS '用户偏好记忆：显式设置或 Agent 推断的配置项，key-value 形式';
COMMENT ON COLUMN user_preferences.id         IS '偏好记录主键，UUID';
COMMENT ON COLUMN user_preferences.user_id    IS '所属用户，级联删除';
COMMENT ON COLUMN user_preferences.key        IS '偏好键，如 search_depth、output_lang、report_style';
COMMENT ON COLUMN user_preferences.value      IS '偏好值，JSONB 支持任意类型（字符串、数字、数组等）';
COMMENT ON COLUMN user_preferences.category   IS '来源类型：explicit（用户主动设置）| implicit（Agent 从行为中推断）';
COMMENT ON COLUMN user_preferences.confidence IS '隐式偏好的置信度（0~1），explicit 类型可为 NULL';
COMMENT ON COLUMN user_preferences.updated_at IS '最后更新时间，由触发器自动维护';
COMMENT ON COLUMN user_preferences.created_at IS '偏好首次记录时间';

CREATE TRIGGER trg_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------

CREATE TABLE skill_memories (
    id               UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    title            VARCHAR(255) NOT NULL,
    content          TEXT         NOT NULL,
    citation         TEXT,
    scope            VARCHAR(20)  NOT NULL DEFAULT 'global',
    user_id          UUID         REFERENCES users(id) ON DELETE SET NULL,
    trigger_patterns JSONB        NOT NULL DEFAULT '[]',
    usage_count      INTEGER      NOT NULL DEFAULT 0,
    last_used_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  skill_memories                  IS 'Skill 记忆：操作 SOP 库，三层结构（title/content/citation）按需加载';
COMMENT ON COLUMN skill_memories.id               IS 'Skill 记忆主键，UUID';
COMMENT ON COLUMN skill_memories.title            IS '一级：关键词/标题，用于快速匹配和索引，加载成本最低';
COMMENT ON COLUMN skill_memories.content          IS '二级：完整 SOP 步骤内容，命中后加载';
COMMENT ON COLUMN skill_memories.citation         IS '三级：引用与解释，含来源说明、边界条件、例外情况，需溯源时加载；可为空';
COMMENT ON COLUMN skill_memories.scope            IS '作用范围：global（系统内置，所有用户可用）| user（用户私有）';
COMMENT ON COLUMN skill_memories.user_id          IS 'scope=user 时关联的用户；scope=global 时为 NULL；用户删除后置 NULL，skill 保留';
COMMENT ON COLUMN skill_memories.trigger_patterns IS '触发匹配关键词列表，格式 ["关键词1", "关键词2"]，用于意图匹配';
COMMENT ON COLUMN skill_memories.usage_count      IS '累计被调用次数';
COMMENT ON COLUMN skill_memories.last_used_at     IS '最后一次被调用的时间，NULL 表示从未使用';
COMMENT ON COLUMN skill_memories.created_at       IS 'Skill 创建时间';
COMMENT ON COLUMN skill_memories.updated_at       IS 'Skill 最后更新时间，由触发器自动维护';

CREATE TRIGGER trg_skill_memories_updated_at
    BEFORE UPDATE ON skill_memories
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 索引
-- =============================================================================

-- FK 索引（PostgreSQL 不自动为外键建索引）
CREATE INDEX idx_topics_user_id             ON topics(user_id);
CREATE INDEX idx_search_tasks_user_id       ON search_tasks(user_id);
CREATE INDEX idx_search_tasks_topic_id      ON search_tasks(topic_id);
CREATE INDEX idx_search_tasks_status        ON search_tasks(status);
CREATE INDEX idx_knowledge_chunks_report_id ON knowledge_chunks(report_id);
CREATE INDEX idx_search_histories_user_id   ON search_histories(user_id);
CREATE INDEX idx_search_histories_topic_id  ON search_histories(topic_id);
CREATE INDEX idx_search_histories_report_id ON search_histories(report_id);
CREATE INDEX idx_working_sessions_user_id   ON working_sessions(user_id);
CREATE INDEX idx_working_sessions_task_id   ON working_sessions(task_id);
CREATE INDEX idx_episodic_logs_user_id      ON episodic_logs(user_id);
CREATE INDEX idx_episodic_logs_task_id      ON episodic_logs(task_id);
CREATE INDEX idx_episodic_logs_session_key  ON episodic_logs(session_key);
CREATE INDEX idx_semantic_memories_user_id  ON semantic_memories(user_id);
CREATE INDEX idx_user_preferences_user_id   ON user_preferences(user_id);
CREATE INDEX idx_skill_memories_scope       ON skill_memories(scope);

-- 业务查询索引
CREATE INDEX idx_search_histories_user_topic ON search_histories(user_id, topic_id);     -- version 计算：统计同 topic 下已有条数
CREATE INDEX idx_user_preferences_user_key   ON user_preferences(user_id, key);          -- 按 key 查单条偏好
CREATE INDEX idx_episodic_logs_user_time     ON episodic_logs(user_id, created_at DESC);  -- 按时间倒序查日志

-- 向量索引（数据量小时全表扫描足够，超过 10 万行后取消注释启用）
-- CREATE INDEX idx_knowledge_chunks_embedding  ON knowledge_chunks  USING hnsw (embedding vector_cosine_ops);
-- CREATE INDEX idx_semantic_memories_embedding ON semantic_memories USING hnsw (embedding vector_cosine_ops);
