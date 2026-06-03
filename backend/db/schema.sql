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
-- 用户 Token 余额与消耗记录
-- =============================================================================

CREATE TABLE user_token_balance (
    user_id        VARCHAR(100) PRIMARY KEY,
    balance        INT          NOT NULL DEFAULT 0,
    total_consumed INT          NOT NULL DEFAULT 0,
    last_reset_at  TIMESTAMPTZ,
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  user_token_balance                IS '用户 token 余额表，记录可用余额和历史总消耗';
COMMENT ON COLUMN user_token_balance.user_id        IS '用户 ID，使用字符串形式兼容注册用户、游客和外部账号';
COMMENT ON COLUMN user_token_balance.balance        IS '剩余 token 数量';
COMMENT ON COLUMN user_token_balance.total_consumed IS '历史累计实际消耗 token 数量';
COMMENT ON COLUMN user_token_balance.last_reset_at  IS '最近一次余额重置时间';
COMMENT ON COLUMN user_token_balance.updated_at     IS '余额最近更新时间，由触发器自动维护';

CREATE TRIGGER trg_user_token_balance_updated_at
    BEFORE UPDATE ON user_token_balance
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE token_consumption_log (
    id               BIGSERIAL    PRIMARY KEY,
    user_id          VARCHAR(100) NOT NULL,
    task_id          VARCHAR(100),
    stage            VARCHAR(50),
    provider         VARCHAR(50),
    model            VARCHAR(100),
    input_tokens     INT          NOT NULL DEFAULT 0,
    output_tokens    INT          NOT NULL DEFAULT 0,
    estimated_before INT          NOT NULL DEFAULT 0,
    actual_consumed  INT          NOT NULL DEFAULT 0,
    balance_after    INT          NOT NULL DEFAULT 0,
    metadata         JSONB        NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  token_consumption_log                  IS 'token 扣减记录表，每次任务结束由记忆管理子 Agent 写入一条流水';
COMMENT ON COLUMN token_consumption_log.id               IS '扣减流水主键，自增';
COMMENT ON COLUMN token_consumption_log.user_id          IS '用户 ID，关联 user_token_balance.user_id';
COMMENT ON COLUMN token_consumption_log.task_id          IS '任务 ID，字符串形式兼容异步任务来源';
COMMENT ON COLUMN token_consumption_log.stage            IS 'token 消耗阶段，例如 planner、retrieve、sort、context_manager';
COMMENT ON COLUMN token_consumption_log.provider         IS '模型或工具提供商';
COMMENT ON COLUMN token_consumption_log.model            IS '具体模型名';
COMMENT ON COLUMN token_consumption_log.input_tokens     IS '该阶段输入 token 数量';
COMMENT ON COLUMN token_consumption_log.output_tokens    IS '该阶段输出 token 数量';
COMMENT ON COLUMN token_consumption_log.estimated_before IS '任务开始前预估 token 消耗';
COMMENT ON COLUMN token_consumption_log.actual_consumed  IS '任务结束后的实际 token 消耗';
COMMENT ON COLUMN token_consumption_log.balance_after    IS '扣减后的 token 余额';
COMMENT ON COLUMN token_consumption_log.metadata         IS '阶段级扩展元数据，例如时间戳和原始 breakdown';
COMMENT ON COLUMN token_consumption_log.created_at       IS '扣减记录创建时间';

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
    search_mode   VARCHAR(20)  NOT NULL DEFAULT 'mixed',
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
    token_usage         JSONB        NOT NULL DEFAULT '{"total": 0, "breakdown": {}, "model_used": {}, "timestamp": null}',
    cost_usage          JSONB        NOT NULL DEFAULT '{"total_usd": 0, "breakdown": {}, "timestamp": null}',
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
COMMENT ON COLUMN reports.token_usage          IS '此次任务消耗的 token 数量，按 search/sort/retrieve/planner/memory_manager/context_manager 等环节细分';
COMMENT ON COLUMN reports.cost_usage           IS '此次任务调用搜索 API、爬虫和 MCP 等外部能力的估算成本与额度消耗';
COMMENT ON COLUMN reports.user_satisfaction    IS '用户满意度：dissatisfied / neutral / satisfied';
COMMENT ON COLUMN reports.satisfaction_notes   IS '用户不满意的具体描述';
COMMENT ON COLUMN reports.created_at           IS '报告生成时间';

-- =============================================================================
-- 知识切片表
-- =============================================================================

CREATE TABLE knowledge_chunks (
    id                BIGSERIAL    PRIMARY KEY,
    report_id         BIGINT       NOT NULL,
    chunk_index       INTEGER      NOT NULL,
    section_title     VARCHAR(500),
    section_level     INTEGER,
    section_anchor    VARCHAR(255),
    parent_title      VARCHAR(500),
    content           TEXT         NOT NULL,
    content_marked    TEXT,
    summary           TEXT,
    source_search_ids BIGINT[]     NOT NULL DEFAULT '{}',
    embedding         vector(1024) NOT NULL,
    metadata          JSONB        NOT NULL DEFAULT '{}',
    search_vector     tsvector     GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(section_title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(summary, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(content, '')), 'B')
    ) STORED
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
COMMENT ON COLUMN knowledge_chunks.content_marked IS '与前一版本对比后的带标记 HTML；del 表示删除，ins.added 表示新增，ins.modified 表示修改';
COMMENT ON COLUMN knowledge_chunks.summary        IS '切片内容摘要（50-150字），用于检索预览和快速筛选';
COMMENT ON COLUMN knowledge_chunks.source_search_ids IS '切片引用的原始搜索历史 ID 集合，通过 search_histories.id 反查来源详情';
COMMENT ON COLUMN knowledge_chunks.embedding      IS '切片摘要的向量表示，维度 1024';
COMMENT ON COLUMN knowledge_chunks.metadata       IS '扩展元数据，不存重复来源详情，来源通过 source_search_ids 反查';
COMMENT ON COLUMN knowledge_chunks.search_vector  IS 'PostgreSQL tsvector 关键词检索列，基于 section_title、summary、content 自动生成';

-- =============================================================================
-- 搜索历史表
-- =============================================================================

CREATE TABLE search_histories (
    id                 BIGSERIAL    PRIMARY KEY,
    parent_id          BIGINT,
    user_id            BIGINT       NOT NULL,
    task_id            BIGINT       NOT NULL,
    topic_id           BIGINT,
    report_id          BIGINT,
    query              TEXT         NOT NULL,
    source_sites       JSONB        NOT NULL DEFAULT '[]',
    search_mode        VARCHAR(20)  NOT NULL DEFAULT 'mixed',
    status             VARCHAR(20)  NOT NULL DEFAULT 'completed',
    result_count       INTEGER      NOT NULL DEFAULT 0,
    retry_count        INTEGER      NOT NULL DEFAULT 0,
    execution_duration INTEGER,
    failure_reason     TEXT,
    raw_results        JSONB        NOT NULL DEFAULT '[]',
    metadata           JSONB        NOT NULL DEFAULT '{}',
    version            INTEGER      NOT NULL DEFAULT 1,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  search_histories              IS '用户搜索历史，原始搜索结果存储';
COMMENT ON COLUMN search_histories.id           IS '历史记录主键，自增';
COMMENT ON COLUMN search_histories.parent_id    IS '父级搜索历史 ID；NULL 表示整体搜索记录，非 NULL 表示子任务搜索记录';
COMMENT ON COLUMN search_histories.user_id      IS '所属用户 ID（关联 users.id）';
COMMENT ON COLUMN search_histories.task_id      IS '关联任务 ID（关联 search_tasks.id）';
COMMENT ON COLUMN search_histories.topic_id     IS '关联主题 ID（关联 topics.id）';
COMMENT ON COLUMN search_histories.report_id    IS '关联报告 ID（关联 reports.id）';
COMMENT ON COLUMN search_histories.query        IS '搜索查询文本';
COMMENT ON COLUMN search_histories.source_sites IS '本次实际执行的搜索来源集合，而不是任务期望来源';
COMMENT ON COLUMN search_histories.search_mode  IS '本次实际执行的搜索方式：api / crawl / mixed';
COMMENT ON COLUMN search_histories.status       IS '本次搜索执行状态：completed / partial / failed';
COMMENT ON COLUMN search_histories.result_count IS '本次搜索返回的有效结果数量';
COMMENT ON COLUMN search_histories.retry_count  IS '本次搜索重试次数';
COMMENT ON COLUMN search_histories.execution_duration IS '本次搜索耗时（秒）';
COMMENT ON COLUMN search_histories.failure_reason IS '本次搜索失败或部分失败原因';
COMMENT ON COLUMN search_histories.raw_results  IS '原始搜索结果 JSON，结果项需要保留来源、标题、URL、发布时间、摘要等详情';
COMMENT ON COLUMN search_histories.metadata     IS '搜索策略、限流退避、扩展关键词、质量摘要等扩展元数据';
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
    importance  FLOAT        NOT NULL DEFAULT 0.5,
    metadata    JSONB        NOT NULL DEFAULT '{}',
    deleted_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  zr_episodic_logs             IS '情景记忆：系统流水账日记，按事件类型记录每次对话和任务执行过程';
COMMENT ON COLUMN zr_episodic_logs.id          IS '情景日志主键，自增';
COMMENT ON COLUMN zr_episodic_logs.user_id     IS '所属用户 ID（关联 users.id）';
COMMENT ON COLUMN zr_episodic_logs.task_id     IS '关联搜索任务 ID（关联 search_tasks.id）';
COMMENT ON COLUMN zr_episodic_logs.session_key IS '关联工作记忆的 session_key';
COMMENT ON COLUMN zr_episodic_logs.event_type  IS '事件类型：conversation（对话）| task_run（任务执行）| search（搜索动作）| error（异常）';
COMMENT ON COLUMN zr_episodic_logs.content     IS '事件完整内容';
COMMENT ON COLUMN zr_episodic_logs.importance  IS '情景记忆重要性评分（0~1），用于淘汰排序';
COMMENT ON COLUMN zr_episodic_logs.metadata    IS '扩展上下文，如 token 消耗、耗时、模型版本等';
COMMENT ON COLUMN zr_episodic_logs.deleted_at  IS '逻辑删除时间，非 NULL 表示已删除或已淘汰';
COMMENT ON COLUMN zr_episodic_logs.created_at  IS '事件发生时间';

-- -----------------------------------------------------------------------------

CREATE TABLE zr_semantic_memories (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     BIGINT,
    title       VARCHAR(500) NOT NULL,
    summary     TEXT         NOT NULL,
    content     TEXT         NOT NULL,
    embedding   vector(1024) NOT NULL,
    source_type VARCHAR(50),
    source_id   BIGINT,
    confidence  FLOAT        NOT NULL DEFAULT 0.5,
    last_accessed TIMESTAMPTZ,
    deleted_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  zr_semantic_memories             IS '语义记忆：从对话和任务中提炼的知识规律，embedding 基于 summary 计算，支持向量检索';
COMMENT ON COLUMN zr_semantic_memories.id          IS '语义记忆主键，自增';
COMMENT ON COLUMN zr_semantic_memories.user_id     IS '所属用户 ID（关联 users.id）；NULL 表示全局记忆';
COMMENT ON COLUMN zr_semantic_memories.title       IS '一句话概括，用于快速索引和展示';
COMMENT ON COLUMN zr_semantic_memories.summary     IS '精简摘要，用于快速预览；embedding 基于此字段计算';
COMMENT ON COLUMN zr_semantic_memories.content     IS '完整内容，向量检索命中后按需加载';
COMMENT ON COLUMN zr_semantic_memories.embedding   IS 'summary 的向量表示，维度 1024；用于语义相似度检索';
COMMENT ON COLUMN zr_semantic_memories.source_type IS '知识来源类型：report（来自报告）| conversation（来自对话）| manual（手动录入）';
COMMENT ON COLUMN zr_semantic_memories.source_id   IS '来源记录 ID，与 source_type 配合使用，可为空';
COMMENT ON COLUMN zr_semantic_memories.confidence  IS '语义记忆置信度（0~1），用于排序和淘汰';
COMMENT ON COLUMN zr_semantic_memories.last_accessed IS '最近使用时间，用于淘汰排序';
COMMENT ON COLUMN zr_semantic_memories.deleted_at  IS '逻辑删除时间，非 NULL 表示已删除或已淘汰';
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
    "desc"           TEXT,
    content          TEXT         NOT NULL,
    citation         TEXT,
    scope            VARCHAR(20)  NOT NULL DEFAULT 'global',
    user_id          BIGINT,
    trigger_patterns JSONB        NOT NULL DEFAULT '[]',
    usage_count      INTEGER      NOT NULL DEFAULT 0,
    success_count    INTEGER      NOT NULL DEFAULT 0,
    fail_count       INTEGER      NOT NULL DEFAULT 0,
    last_used_at     TIMESTAMPTZ,
    status           TEXT         NOT NULL DEFAULT 'active',
    confidence       FLOAT        NOT NULL DEFAULT 0.5,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  zr_skill_memories                  IS 'Skill 记忆：操作 SOP 库，四段式结构（title/desc/content/citation）按阶段加载';
COMMENT ON COLUMN zr_skill_memories.id               IS 'Skill 记忆主键，自增';
COMMENT ON COLUMN zr_skill_memories.title            IS 'Skill 名字，用于快速匹配、展示和索引';
COMMENT ON COLUMN zr_skill_memories."desc"           IS 'Skill 描述，作为第一阶段加载内容，用于判断是否需要加载完整 SOP';
COMMENT ON COLUMN zr_skill_memories.content          IS '完整 SOP 步骤内容，命中后第二阶段加载';
COMMENT ON COLUMN zr_skill_memories.citation         IS '引用与解释，含来源说明、边界条件、例外情况，按需第三阶段加载';
COMMENT ON COLUMN zr_skill_memories.scope            IS '作用范围：global（系统内置）| user（用户私有）';
COMMENT ON COLUMN zr_skill_memories.user_id          IS 'scope=user 时关联的用户 ID（关联 users.id）';
COMMENT ON COLUMN zr_skill_memories.trigger_patterns IS '触发匹配关键词列表，格式 ["关键词1", "关键词2"]';
COMMENT ON COLUMN zr_skill_memories.usage_count      IS '累计被调用次数';
COMMENT ON COLUMN zr_skill_memories.success_count    IS '成功使用次数';
COMMENT ON COLUMN zr_skill_memories.fail_count       IS '失败次数';
COMMENT ON COLUMN zr_skill_memories.last_used_at     IS '最后一次被调用的时间，NULL 表示从未使用';
COMMENT ON COLUMN zr_skill_memories.status           IS '有效性状态：active（可用）| deprecated（已废弃）| archived（已归档）';
COMMENT ON COLUMN zr_skill_memories.confidence       IS 'Skill 置信度，默认 0.5，可按成功次数 / 总次数计算';
COMMENT ON COLUMN zr_skill_memories.created_at       IS 'Skill 创建时间';
COMMENT ON COLUMN zr_skill_memories.updated_at       IS 'Skill 最后更新时间，由触发器自动维护';

CREATE TRIGGER trg_zr_skill_memories_updated_at
    BEFORE UPDATE ON zr_skill_memories
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 护栏审计表
-- =============================================================================

CREATE TABLE log_guardrail (
    id                BIGSERIAL    PRIMARY KEY,
    user_id           BIGINT,
    task_id           BIGINT,
    agent_name        VARCHAR(50)  NOT NULL,
    hook              VARCHAR(50)  NOT NULL,
    operation         VARCHAR(255),
    tool_name         VARCHAR(128),
    allowed           BOOLEAN      NOT NULL,
    alert_level       VARCHAR(20)  NOT NULL,
    reason            TEXT,
    sanitized_payload JSONB        NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE  log_guardrail                   IS 'Pydantic AI Agent 护栏审计表，归档 warning/critical 等需要长期保留的护栏决策';
COMMENT ON COLUMN log_guardrail.id                IS '护栏审计主键，自增';
COMMENT ON COLUMN log_guardrail.user_id           IS '关联用户 ID，可为空';
COMMENT ON COLUMN log_guardrail.task_id           IS '关联任务 ID，可为空';
COMMENT ON COLUMN log_guardrail.agent_name        IS '触发护栏的 Agent 名称';
COMMENT ON COLUMN log_guardrail.hook              IS '触发 hook，如 before_run、before_tool_call、after_tool_call、on_error';
COMMENT ON COLUMN log_guardrail.operation         IS '被检查的操作名称';
COMMENT ON COLUMN log_guardrail.tool_name         IS '被检查的 Tool 名称，可为空';
COMMENT ON COLUMN log_guardrail.allowed           IS '护栏是否允许继续执行';
COMMENT ON COLUMN log_guardrail.alert_level       IS '审计级别：info / warning / critical';
COMMENT ON COLUMN log_guardrail.reason            IS '护栏决策原因';
COMMENT ON COLUMN log_guardrail.sanitized_payload IS '脱敏后的上下文快照，禁止保存 token、password、authorization 等敏感字段';
COMMENT ON COLUMN log_guardrail.created_at        IS '审计记录创建时间';

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
CREATE INDEX idx_search_histories_mode_status ON search_histories(search_mode, status);
CREATE INDEX idx_search_histories_source_sites ON search_histories USING GIN(source_sites);
CREATE INDEX idx_knowledge_chunks_search_vector ON knowledge_chunks USING GIN(search_vector);
CREATE INDEX idx_zr_working_sessions_user_id   ON zr_working_sessions(user_id);
CREATE INDEX idx_zr_working_sessions_task_id   ON zr_working_sessions(task_id);
CREATE INDEX idx_zr_episodic_logs_user_id      ON zr_episodic_logs(user_id);
CREATE INDEX idx_zr_episodic_logs_task_id      ON zr_episodic_logs(task_id);
CREATE INDEX idx_zr_episodic_logs_session_key  ON zr_episodic_logs(session_key);
CREATE INDEX idx_zr_episodic_logs_event_type   ON zr_episodic_logs(event_type);
CREATE INDEX idx_zr_semantic_memories_user_id  ON zr_semantic_memories(user_id);
CREATE INDEX idx_zr_user_preferences_user_id   ON zr_user_preferences(user_id);
CREATE INDEX idx_zr_skill_memories_scope       ON zr_skill_memories(scope);
CREATE INDEX idx_zr_skill_memories_status      ON zr_skill_memories(status);
CREATE INDEX idx_log_guardrail_task_time       ON log_guardrail(task_id, created_at DESC);
CREATE INDEX idx_log_guardrail_level_time      ON log_guardrail(alert_level, created_at DESC);
CREATE INDEX idx_log_guardrail_agent_hook      ON log_guardrail(agent_name, hook);
CREATE INDEX idx_token_consumption_log_user_time ON token_consumption_log(user_id, created_at DESC);
CREATE INDEX idx_token_consumption_log_task      ON token_consumption_log(task_id);

-- 复合索引（覆盖高频排序 + 过滤组合）
CREATE INDEX idx_topics_user_created            ON topics(user_id, created_at DESC);
CREATE INDEX idx_search_tasks_user_created      ON search_tasks(user_id, created_at DESC);
CREATE INDEX idx_search_histories_user_created  ON search_histories(user_id, created_at DESC);
CREATE INDEX idx_search_histories_user_topic    ON search_histories(user_id, topic_id);
CREATE INDEX idx_knowledge_chunks_report_chunk  ON knowledge_chunks(report_id, chunk_index);
CREATE INDEX idx_knowledge_chunks_source_search_ids ON knowledge_chunks USING GIN(source_search_ids);
CREATE INDEX idx_zr_episodic_logs_user_time        ON zr_episodic_logs(user_id, created_at DESC);
CREATE INDEX idx_zr_episodic_logs_eviction         ON zr_episodic_logs(user_id, deleted_at, importance, created_at);
CREATE INDEX idx_zr_semantic_memories_eviction     ON zr_semantic_memories(user_id, deleted_at, confidence, last_accessed);
CREATE INDEX idx_zr_skill_memories_eviction        ON zr_skill_memories(scope, user_id, status, confidence, last_used_at);

-- 向量索引统一使用 HNSW。
CREATE INDEX idx_knowledge_chunks_embedding  ON knowledge_chunks  USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_zr_semantic_memories_embedding ON zr_semantic_memories USING hnsw (embedding vector_cosine_ops);
