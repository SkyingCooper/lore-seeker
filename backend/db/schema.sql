-- =============================================================================
-- Lore Seeker · PostgreSQL Schema
-- =============================================================================
-- 执行方式：psql -U <user> -d <db> -f schema.sql
--
-- 设计说明：
--   主键统一使用 BIGSERIAL（自增 ID），避免 UUID 的 B-tree 页分裂问题。
--   不使用外键约束，数据一致性由应用层（SQLAlchemy）保证。
--   列名保留 user_id / topic_id / task_id / report_id 表关联语义，
--   通过索引加速 JOIN 查询，级联删除逻辑在应用层处理。
-- =============================================================================

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
-- 用户表
-- =============================================================================

CREATE TABLE users (
    id              BIGSERIAL    PRIMARY KEY,
    username        VARCHAR(64)  UNIQUE,
    email           VARCHAR(255) UNIQUE,
    hashed_password VARCHAR(255),
    avatar_url      VARCHAR(512),
    is_guest        BOOLEAN      NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  users                 IS '用户表，支持游客（Session Cookie）与注册用户（JWT）两种身份';
COMMENT ON COLUMN users.id              IS '用户主键，自增';
COMMENT ON COLUMN users.username        IS '用户名，注册用户必填且唯一，游客为 NULL';
COMMENT ON COLUMN users.email           IS '注册用户邮箱，游客为 NULL';
COMMENT ON COLUMN users.hashed_password IS 'bcrypt 哈希密码，游客为 NULL';
COMMENT ON COLUMN users.avatar_url      IS '头像地址，可为空';
COMMENT ON COLUMN users.is_guest        IS '是否游客；TRUE = 游客（Session Cookie 鉴权），FALSE = 注册用户（JWT 鉴权）';
COMMENT ON COLUMN users.last_login_at   IS '最近一次登录时间，注册/登录/升级时更新';
COMMENT ON COLUMN users.created_at      IS '账号创建时间';
COMMENT ON COLUMN users.updated_at      IS '最后修改时间，由触发器自动维护';

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 主题表
-- =============================================================================

CREATE TABLE topics (
    id           BIGSERIAL    PRIMARY KEY,
    user_id      BIGINT       NOT NULL,
    title        VARCHAR(255) NOT NULL,
    keywords     JSONB        NOT NULL DEFAULT '[]',
    description  TEXT,
    deleted_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  topics             IS '用户自定义的搜索主题';
COMMENT ON COLUMN topics.id          IS '主题主键，自增';
COMMENT ON COLUMN topics.user_id     IS '所属用户 ID（关联 users.id）';
COMMENT ON COLUMN topics.title       IS '主题名称';
COMMENT ON COLUMN topics.keywords    IS '关键词列表，如 ["AI","大模型"]';
COMMENT ON COLUMN topics.description IS '主题描述，可为空';
COMMENT ON COLUMN topics.deleted_at  IS '逻辑删除时间，NULL 表示未删除';
COMMENT ON COLUMN topics.created_at  IS '主题创建时间';
COMMENT ON COLUMN topics.updated_at  IS '最后修改时间，由触发器自动维护';

CREATE TRIGGER trg_topics_updated_at
    BEFORE UPDATE ON topics
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 搜索任务表
-- =============================================================================

CREATE TABLE search_tasks (
    id            BIGSERIAL    PRIMARY KEY,
    user_id       BIGINT       NOT NULL,
    topic_id      BIGINT       NOT NULL,
    query         TEXT,
    source_sites  JSONB        NOT NULL DEFAULT '[]',
    search_mode   VARCHAR(20)  NOT NULL DEFAULT 'api',
    frequency     VARCHAR(20)  NOT NULL DEFAULT 'once',
    status        VARCHAR(20)  NOT NULL DEFAULT 'pending',
    deleted_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  search_tasks                IS '任务表，记录搜索任务的配置与生命周期';
COMMENT ON COLUMN search_tasks.id             IS '任务主键，自增';
COMMENT ON COLUMN search_tasks.user_id        IS '所属用户 ID（关联 users.id）';
COMMENT ON COLUMN search_tasks.topic_id       IS '关联主题 ID（关联 topics.id）';
COMMENT ON COLUMN search_tasks.query          IS '快速搜索查询文本，结构化任务为 NULL';
COMMENT ON COLUMN search_tasks.source_sites   IS '来源网站列表';
COMMENT ON COLUMN search_tasks.search_mode    IS '搜索方式：api / crawl / mixed';
COMMENT ON COLUMN search_tasks.frequency      IS '搜索频率：once / daily / weekly / biweekly / monthly';
COMMENT ON COLUMN search_tasks.status         IS '任务状态：pending / fetching / organizing / completed / failed';
COMMENT ON COLUMN search_tasks.deleted_at     IS '逻辑删除时间';
COMMENT ON COLUMN search_tasks.created_at     IS '任务创建时间';
COMMENT ON COLUMN search_tasks.updated_at     IS '最后更新时间，由触发器自动维护';

CREATE TRIGGER trg_search_tasks_updated_at
    BEFORE UPDATE ON search_tasks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 报告表
-- =============================================================================

CREATE TABLE reports (
    id                  BIGSERIAL    PRIMARY KEY,
    topic_id            BIGINT       NOT NULL,
    task_id             BIGINT       NOT NULL,
    status              VARCHAR(20)  NOT NULL DEFAULT 'success',
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    execution_duration  INT,
    failure_reason      TEXT,
    result_count        INT,
    retry_count         INT          NOT NULL DEFAULT 0,
    quality_score       FLOAT,
    content_md          TEXT,
    toc                 JSONB        NOT NULL DEFAULT '[]',
    summary             TEXT,
    user_satisfaction   VARCHAR(20),
    satisfaction_notes  TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  reports                      IS '报告/执行记录表，一次任务执行产生一条报告';
COMMENT ON COLUMN reports.id                   IS '报告主键，自增';
COMMENT ON COLUMN reports.topic_id             IS '关联主题 ID（关联 topics.id）';
COMMENT ON COLUMN reports.task_id              IS '关联任务 ID（关联 search_tasks.id）';
COMMENT ON COLUMN reports.status               IS '执行结果：completed / partial / failed';
COMMENT ON COLUMN reports.started_at           IS '执行开始时间';
COMMENT ON COLUMN reports.finished_at          IS '执行结束时间';
COMMENT ON COLUMN reports.execution_duration   IS '执行耗时（秒）';
COMMENT ON COLUMN reports.failure_reason       IS '失败原因';
COMMENT ON COLUMN reports.result_count         IS '抓取数据条数';
COMMENT ON COLUMN reports.retry_count          IS '节点重试累计次数';
COMMENT ON COLUMN reports.quality_score        IS '大模型评分';
COMMENT ON COLUMN reports.content_md           IS '大模型分析总结（Markdown）';
COMMENT ON COLUMN reports.toc                  IS '报告目录结构';
COMMENT ON COLUMN reports.summary              IS '报告摘要';
COMMENT ON COLUMN reports.user_satisfaction    IS '用户满意度：dissatisfied / neutral / satisfied';
COMMENT ON COLUMN reports.satisfaction_notes   IS '用户不满意的具体描述';
COMMENT ON COLUMN reports.created_at           IS '报告生成时间';

-- =============================================================================
-- 知识切片表
-- =============================================================================

CREATE TABLE knowledge_chunks (
    id             BIGSERIAL    PRIMARY KEY,
    report_id      BIGINT       NOT NULL,
    chunk_index    INTEGER      NOT NULL,
    section_title  VARCHAR(500),
    section_level  INTEGER,
    section_anchor VARCHAR(255),
    parent_title   VARCHAR(500),
    content        TEXT         NOT NULL,
    embedding      vector(1536) NOT NULL,
    metadata       JSONB        NOT NULL DEFAULT '{}'
);
COMMENT ON TABLE  knowledge_chunks                IS '报告按标题分层切片后的向量化存储，支持三层目录导航';
COMMENT ON COLUMN knowledge_chunks.id             IS '切片主键，自增';
COMMENT ON COLUMN knowledge_chunks.report_id      IS '所属报告 ID（关联 reports.id）';
COMMENT ON COLUMN knowledge_chunks.chunk_index    IS '切片在报告中的顺序序号';
COMMENT ON COLUMN knowledge_chunks.section_title  IS '所属章节标题，如"1.1 技术背景"';
COMMENT ON COLUMN knowledge_chunks.section_level  IS '标题层级：1/2/3';
COMMENT ON COLUMN knowledge_chunks.section_anchor IS 'TOC 锚点 slug';
COMMENT ON COLUMN knowledge_chunks.parent_title   IS '父级章节标题，用于构建面包屑导航';
COMMENT ON COLUMN knowledge_chunks.content        IS '切片文本内容';
COMMENT ON COLUMN knowledge_chunks.embedding      IS '切片内容的向量表示，维度 1536';
COMMENT ON COLUMN knowledge_chunks.metadata       IS '扩展元数据，如来源 URL 等';

-- =============================================================================
-- 搜索历史表
-- =============================================================================

CREATE TABLE search_histories (
    id          BIGSERIAL    PRIMARY KEY,
    parent_id   BIGINT,
    user_id     BIGINT       NOT NULL,
    task_id     BIGINT       NOT NULL,
    topic_id    BIGINT,
    report_id   BIGINT,
    query       TEXT         NOT NULL,
    raw_results JSONB        NOT NULL DEFAULT '[]',
    version     INTEGER      NOT NULL DEFAULT 1,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  search_histories              IS '用户搜索历史，原始搜索结果存储';
COMMENT ON COLUMN search_histories.id           IS '历史记录主键，自增';
COMMENT ON COLUMN search_histories.parent_id    IS '父级搜索历史 ID；NULL 表示整体搜索记录，非 NULL 表示子任务搜索记录';
COMMENT ON COLUMN search_histories.user_id      IS '所属用户 ID（关联 users.id）';
COMMENT ON COLUMN search_histories.task_id      IS '关联任务 ID（关联 search_tasks.id）';
COMMENT ON COLUMN search_histories.topic_id     IS '关联主题 ID（关联 topics.id）';
COMMENT ON COLUMN search_histories.report_id    IS '关联报告 ID（关联 reports.id）';
COMMENT ON COLUMN search_histories.query        IS '搜索查询文本';
COMMENT ON COLUMN search_histories.raw_results  IS '原始搜索结果 JSON';
COMMENT ON COLUMN search_histories.version      IS '搜索版本号';
COMMENT ON COLUMN search_histories.created_at   IS '记录创建时间';

-- =============================================================================
-- Agent 五类记忆表
-- =============================================================================

CREATE TABLE zr_working_sessions (
    id           BIGSERIAL    PRIMARY KEY,
    user_id      BIGINT       NOT NULL,
    task_id      BIGINT,
    session_key  VARCHAR(255) NOT NULL UNIQUE,
    goal         TEXT         NOT NULL,
    current_step INTEGER      NOT NULL DEFAULT 0,
    steps        JSONB        NOT NULL DEFAULT '[]',
    tool_cache   JSONB        NOT NULL DEFAULT '{}',
    status       VARCHAR(20)  NOT NULL DEFAULT 'archived',
    started_at   TIMESTAMPTZ  NOT NULL,
    ended_at     TIMESTAMPTZ
);
COMMENT ON TABLE  zr_working_sessions              IS 'Agent 工作记忆归档表；活跃态存于 Redis，会话结束后异步写入并删除 Redis key';
COMMENT ON COLUMN zr_working_sessions.id           IS '工作记忆归档主键，自增';
COMMENT ON COLUMN zr_working_sessions.user_id      IS '所属用户 ID（关联 users.id）';
COMMENT ON COLUMN zr_working_sessions.task_id      IS '关联搜索任务 ID（关联 search_tasks.id）';
COMMENT ON COLUMN zr_working_sessions.session_key  IS 'Redis key（working_session:{session_key}），活跃会话的唯一标识';
COMMENT ON COLUMN zr_working_sessions.goal         IS '本次会话的当前目标描述';
COMMENT ON COLUMN zr_working_sessions.current_step IS 'Agent 执行到第几步，归档时记录最终步骤数';
COMMENT ON COLUMN zr_working_sessions.steps        IS '步骤执行记录列表，格式 [{step, action, result, timestamp}]';
COMMENT ON COLUMN zr_working_sessions.tool_cache   IS '工具调用结果缓存，格式 {tool_name: result}';
COMMENT ON COLUMN zr_working_sessions.status       IS '会话状态：active（Redis 中活跃）| archived（已归档到 DB）';
COMMENT ON COLUMN zr_working_sessions.started_at   IS '会话开始时间';
COMMENT ON COLUMN zr_working_sessions.ended_at     IS '会话结束时间，active 状态时为 NULL';

-- -----------------------------------------------------------------------------

CREATE TABLE zr_episodic_logs (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     BIGINT       NOT NULL,
    task_id     BIGINT,
    session_key VARCHAR(255),
    event_type  VARCHAR(50)  NOT NULL,
    content     TEXT         NOT NULL,
    metadata    JSONB        NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  zr_episodic_logs             IS '情景记忆：系统流水账日记，按事件类型记录每次对话和任务执行过程';
COMMENT ON COLUMN zr_episodic_logs.id          IS '情景日志主键，自增';
COMMENT ON COLUMN zr_episodic_logs.user_id     IS '所属用户 ID（关联 users.id）';
COMMENT ON COLUMN zr_episodic_logs.task_id     IS '关联搜索任务 ID（关联 search_tasks.id）';
COMMENT ON COLUMN zr_episodic_logs.session_key IS '关联工作记忆的 session_key';
COMMENT ON COLUMN zr_episodic_logs.event_type  IS '事件类型：conversation（对话）| task_run（任务执行）| search（搜索动作）| error（异常）';
COMMENT ON COLUMN zr_episodic_logs.content     IS '事件完整内容';
COMMENT ON COLUMN zr_episodic_logs.metadata    IS '扩展上下文，如 token 消耗、耗时、模型版本等';
COMMENT ON COLUMN zr_episodic_logs.created_at  IS '事件发生时间';

-- -----------------------------------------------------------------------------

CREATE TABLE zr_semantic_memories (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     BIGINT,
    title       VARCHAR(500) NOT NULL,
    summary     TEXT         NOT NULL,
    content     TEXT         NOT NULL,
    embedding   vector(1536) NOT NULL,
    source_type VARCHAR(50),
    source_id   BIGINT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  zr_semantic_memories             IS '语义记忆：从对话和任务中提炼的知识规律，embedding 基于 summary 计算，支持向量检索';
COMMENT ON COLUMN zr_semantic_memories.id          IS '语义记忆主键，自增';
COMMENT ON COLUMN zr_semantic_memories.user_id     IS '所属用户 ID（关联 users.id）；NULL 表示全局记忆';
COMMENT ON COLUMN zr_semantic_memories.title       IS '一句话概括，用于快速索引和展示';
COMMENT ON COLUMN zr_semantic_memories.summary     IS '精简摘要，用于快速预览；embedding 基于此字段计算';
COMMENT ON COLUMN zr_semantic_memories.content     IS '完整内容，向量检索命中后按需加载';
COMMENT ON COLUMN zr_semantic_memories.embedding   IS 'summary 的向量表示，维度 1536；用于语义相似度检索';
COMMENT ON COLUMN zr_semantic_memories.source_type IS '知识来源类型：report（来自报告）| conversation（来自对话）| manual（手动录入）';
COMMENT ON COLUMN zr_semantic_memories.source_id   IS '来源记录 ID，与 source_type 配合使用，可为空';
COMMENT ON COLUMN zr_semantic_memories.created_at  IS '记忆创建时间';

-- -----------------------------------------------------------------------------

CREATE TABLE zr_user_preferences (
    id         BIGSERIAL    PRIMARY KEY,
    user_id    BIGINT       NOT NULL,
    key        VARCHAR(255) NOT NULL,
    value      JSONB,
    category   VARCHAR(20)  NOT NULL DEFAULT 'implicit',
    confidence FLOAT,
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  zr_user_preferences            IS '用户偏好记忆：显式设置或 Agent 推断的配置项，key-value 形式';
COMMENT ON COLUMN zr_user_preferences.id         IS '偏好记录主键，自增';
COMMENT ON COLUMN zr_user_preferences.user_id    IS '所属用户 ID（关联 users.id）';
COMMENT ON COLUMN zr_user_preferences.key        IS '偏好键，如 search_depth、output_lang、report_style';
COMMENT ON COLUMN zr_user_preferences.value      IS '偏好值，JSONB 支持任意类型（字符串、数字、数组等）';
COMMENT ON COLUMN zr_user_preferences.category   IS '来源类型：explicit（用户主动设置）| implicit（Agent 从行为中推断）';
COMMENT ON COLUMN zr_user_preferences.confidence IS '隐式偏好的置信度（0~1），explicit 类型可为 NULL';
COMMENT ON COLUMN zr_user_preferences.updated_at IS '最后更新时间，由触发器自动维护';
COMMENT ON COLUMN zr_user_preferences.created_at IS '偏好首次记录时间';

-- 同一用户不允许重复 key
CREATE UNIQUE INDEX uq_zr_user_preferences_user_key ON zr_user_preferences(user_id, key);

CREATE TRIGGER trg_zr_user_preferences_updated_at
    BEFORE UPDATE ON zr_user_preferences
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------

CREATE TABLE zr_skill_memories (
    id               BIGSERIAL    PRIMARY KEY,
    title            VARCHAR(255) NOT NULL,
    content          TEXT         NOT NULL,
    citation         TEXT,
    scope            VARCHAR(20)  NOT NULL DEFAULT 'global',
    user_id          BIGINT,
    trigger_patterns JSONB        NOT NULL DEFAULT '[]',
    usage_count      INTEGER      NOT NULL DEFAULT 0,
    last_used_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  zr_skill_memories                  IS 'Skill 记忆：操作 SOP 库，三层结构（title/content/citation）按需加载';
COMMENT ON COLUMN zr_skill_memories.id               IS 'Skill 记忆主键，自增';
COMMENT ON COLUMN zr_skill_memories.title            IS '一级：关键词/标题，用于快速匹配和索引';
COMMENT ON COLUMN zr_skill_memories.content          IS '二级：完整 SOP 步骤内容，命中后加载';
COMMENT ON COLUMN zr_skill_memories.citation         IS '三级：引用与解释，含来源说明、边界条件、例外情况';
COMMENT ON COLUMN zr_skill_memories.scope            IS '作用范围：global（系统内置）| user（用户私有）';
COMMENT ON COLUMN zr_skill_memories.user_id          IS 'scope=user 时关联的用户 ID（关联 users.id）';
COMMENT ON COLUMN zr_skill_memories.trigger_patterns IS '触发匹配关键词列表，格式 ["关键词1", "关键词2"]';
COMMENT ON COLUMN zr_skill_memories.usage_count      IS '累计被调用次数';
COMMENT ON COLUMN zr_skill_memories.last_used_at     IS '最后一次被调用的时间，NULL 表示从未使用';
COMMENT ON COLUMN zr_skill_memories.created_at       IS 'Skill 创建时间';
COMMENT ON COLUMN zr_skill_memories.updated_at       IS 'Skill 最后更新时间，由触发器自动维护';

CREATE TRIGGER trg_zr_skill_memories_updated_at
    BEFORE UPDATE ON zr_skill_memories
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 索引
-- =============================================================================

-- 关联列索引（加速 JOIN 查询）
CREATE INDEX idx_topics_user_id             ON topics(user_id);
CREATE INDEX idx_search_tasks_user_id       ON search_tasks(user_id);
CREATE INDEX idx_search_tasks_topic_id      ON search_tasks(topic_id);
CREATE INDEX idx_search_tasks_status        ON search_tasks(status);
CREATE INDEX idx_knowledge_chunks_report_id ON knowledge_chunks(report_id);
CREATE INDEX idx_search_histories_user_id   ON search_histories(user_id);
CREATE INDEX idx_search_histories_parent_id ON search_histories(parent_id);
CREATE INDEX idx_search_histories_topic_id  ON search_histories(topic_id);
CREATE INDEX idx_search_histories_report_id ON search_histories(report_id);
CREATE INDEX idx_zr_working_sessions_user_id   ON zr_working_sessions(user_id);
CREATE INDEX idx_zr_working_sessions_task_id   ON zr_working_sessions(task_id);
CREATE INDEX idx_zr_episodic_logs_user_id      ON zr_episodic_logs(user_id);
CREATE INDEX idx_zr_episodic_logs_task_id      ON zr_episodic_logs(task_id);
CREATE INDEX idx_zr_episodic_logs_session_key  ON zr_episodic_logs(session_key);
CREATE INDEX idx_zr_episodic_logs_event_type   ON zr_episodic_logs(event_type);
CREATE INDEX idx_zr_semantic_memories_user_id  ON zr_semantic_memories(user_id);
CREATE INDEX idx_zr_user_preferences_user_id   ON zr_user_preferences(user_id);
CREATE INDEX idx_zr_skill_memories_scope       ON zr_skill_memories(scope);

-- 复合索引（覆盖高频排序 + 过滤组合）
CREATE INDEX idx_topics_user_created            ON topics(user_id, created_at DESC);
CREATE INDEX idx_search_tasks_user_created      ON search_tasks(user_id, created_at DESC);
CREATE INDEX idx_search_histories_user_created  ON search_histories(user_id, created_at DESC);
CREATE INDEX idx_search_histories_user_topic    ON search_histories(user_id, topic_id);
CREATE INDEX idx_knowledge_chunks_report_chunk  ON knowledge_chunks(report_id, chunk_index);
CREATE INDEX idx_zr_episodic_logs_user_time        ON zr_episodic_logs(user_id, created_at DESC);

-- 向量索引（数据量小时全表扫描足够，超过 10 万行后取消注释启用）
-- CREATE INDEX idx_knowledge_chunks_embedding  ON knowledge_chunks  USING hnsw (embedding vector_cosine_ops);
-- CREATE INDEX idx_zr_semantic_memories_embedding ON zr_semantic_memories USING hnsw (embedding vector_cosine_ops);
