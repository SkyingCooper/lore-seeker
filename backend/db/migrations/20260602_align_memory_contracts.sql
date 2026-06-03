-- 文件说明：
-- 将已存在的旧记忆表迁移到当前统一的 zr_* 命名，并补齐本轮设计落地所需字段。
-- 该脚本使用 IF EXISTS / IF NOT EXISTS，适合在已有环境中执行；执行前仍应先备份数据库。

BEGIN;

DO $$
BEGIN
    IF to_regclass('public.working_sessions') IS NOT NULL
       AND to_regclass('public.zr_working_sessions') IS NULL THEN
        ALTER TABLE working_sessions RENAME TO zr_working_sessions;
    END IF;

    IF to_regclass('public.episodic_logs') IS NOT NULL
       AND to_regclass('public.zr_episodic_logs') IS NULL THEN
        ALTER TABLE episodic_logs RENAME TO zr_episodic_logs;
    END IF;

    IF to_regclass('public.semantic_memories') IS NOT NULL
       AND to_regclass('public.zr_semantic_memories') IS NULL THEN
        ALTER TABLE semantic_memories RENAME TO zr_semantic_memories;
    END IF;

    IF to_regclass('public.user_preferences') IS NOT NULL
       AND to_regclass('public.zr_user_preferences') IS NULL THEN
        ALTER TABLE user_preferences RENAME TO zr_user_preferences;
    END IF;

    IF to_regclass('public.skill_memories') IS NOT NULL
       AND to_regclass('public.zr_skill_memories') IS NULL THEN
        ALTER TABLE skill_memories RENAME TO zr_skill_memories;
    END IF;
END $$;

ALTER TABLE IF EXISTS reports
    ADD COLUMN IF NOT EXISTS token_usage JSONB DEFAULT '{}'::jsonb;

ALTER TABLE IF EXISTS knowledge_chunks
    ADD COLUMN IF NOT EXISTS content_marked TEXT,
    ADD COLUMN IF NOT EXISTS summary TEXT,
    ADD COLUMN IF NOT EXISTS source_search_ids BIGINT[] DEFAULT '{}'::BIGINT[];

ALTER TABLE IF EXISTS search_histories
    ADD COLUMN IF NOT EXISTS parent_id BIGINT REFERENCES search_histories(id),
    ADD COLUMN IF NOT EXISTS source_sites JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS search_mode VARCHAR(20) DEFAULT 'mixed',
    ADD COLUMN IF NOT EXISTS execution_duration INTEGER,
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

ALTER TABLE IF EXISTS zr_semantic_memories
    ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT 0.5,
    ADD COLUMN IF NOT EXISTS last_accessed TIMESTAMP,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

ALTER TABLE IF EXISTS zr_episodic_logs
    ADD COLUMN IF NOT EXISTS importance FLOAT DEFAULT 0.5,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

ALTER TABLE IF EXISTS zr_skill_memories
    ADD COLUMN IF NOT EXISTS "desc" TEXT,
    ADD COLUMN IF NOT EXISTS success_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS fail_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT 0.5;

CREATE TABLE IF NOT EXISTS log_guardrail (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    task_id BIGINT,
    agent_name VARCHAR(50) NOT NULL,
    hook VARCHAR(50) NOT NULL,
    operation VARCHAR(255),
    tool_name VARCHAR(128),
    allowed BOOLEAN NOT NULL,
    alert_level VARCHAR(20) NOT NULL,
    reason TEXT,
    sanitized_payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_token_balance (
    user_id VARCHAR(100) PRIMARY KEY,
    balance INT DEFAULT 0,
    total_consumed INT DEFAULT 0,
    last_reset_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS token_consumption_log (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    task_id VARCHAR(100),
    estimated_before INT DEFAULT 0,
    actual_consumed INT DEFAULT 0,
    balance_after INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_zr_user_preferences_user_key
    ON zr_user_preferences(user_id, key);
CREATE INDEX IF NOT EXISTS idx_zr_working_sessions_user_id
    ON zr_working_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_zr_working_sessions_task_id
    ON zr_working_sessions(task_id);
CREATE INDEX IF NOT EXISTS idx_zr_episodic_logs_user_time
    ON zr_episodic_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_zr_episodic_logs_eviction
    ON zr_episodic_logs(user_id, deleted_at, importance, created_at);
CREATE INDEX IF NOT EXISTS idx_zr_semantic_memories_eviction
    ON zr_semantic_memories(user_id, deleted_at, confidence, last_accessed);
CREATE INDEX IF NOT EXISTS idx_zr_skill_memories_status
    ON zr_skill_memories(status);
CREATE INDEX IF NOT EXISTS idx_zr_skill_memories_eviction
    ON zr_skill_memories(scope, user_id, status, confidence, last_used_at);
CREATE INDEX IF NOT EXISTS idx_log_guardrail_task
    ON log_guardrail(task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_log_guardrail_level
    ON log_guardrail(alert_level, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_token_consumption_log_user_time
    ON token_consumption_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_token_consumption_log_task
    ON token_consumption_log(task_id);

-- 向量维度统一为 1024。若表中已有 1536 维历史数据，应先清理或重新生成向量后再启用下列语句。
-- ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(1024);
-- ALTER TABLE zr_semantic_memories ALTER COLUMN embedding TYPE vector(1024);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_zr_semantic_memories_embedding
    ON zr_semantic_memories USING hnsw (embedding vector_cosine_ops);

COMMENT ON TABLE log_guardrail IS 'Agent 护栏审计归档表，保存 warning / critical 级决策';
COMMENT ON COLUMN reports.token_usage IS '本次任务 token 消耗统计，按 Agent/环节细分';
COMMENT ON COLUMN knowledge_chunks.content_marked IS '与上一版本对比后的标记 HTML';
COMMENT ON COLUMN knowledge_chunks.summary IS '切片摘要，50-150 字，用于检索预览和向量化';
COMMENT ON COLUMN knowledge_chunks.source_search_ids IS '该切片来源的 search_histories.id 集合';
COMMENT ON COLUMN zr_skill_memories."desc" IS 'Skill 描述，作为第一阶段加载内容';
COMMENT ON TABLE user_token_balance IS '用户 token 余额表，记录剩余余额和历史累计消耗';
COMMENT ON TABLE token_consumption_log IS 'token 扣减流水表，每次任务结束写入一条记录';

COMMIT;
