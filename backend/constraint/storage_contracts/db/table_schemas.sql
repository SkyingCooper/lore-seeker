-- Lore Seeker DB table contract snapshot.
-- Source of truth remains backend/db/schema.sql.
-- This file defines table names, ownership, and cross-table constraints expected by Agents.

-- Core business chain:
-- users -> topics -> search_tasks -> reports -> knowledge_chunks
-- users -> user_token_balance -> token_consumption_log

-- Agent memory tables use the zr_ prefix.
-- Required tables:
--   zr_working_sessions
--   zr_episodic_logs
--   zr_semantic_memories
--   zr_user_preferences
--   zr_skill_memories
--   log_guardrail
--   user_token_balance
--   token_consumption_log

-- Required ownership constraints:
--   topics.user_id -> users.id
--   search_tasks.user_id -> users.id
--   search_tasks.topic_id -> topics.id
--   reports.task_id -> search_tasks.id
--   knowledge_chunks.report_id -> reports.id
--   knowledge_chunks.source_search_ids contains search_histories.id values for source traceability
--   search_histories.user_id -> users.id
--   search_histories.task_id -> search_tasks.id
--   search_histories.parent_id -> search_histories.id for subtask-level histories
--   zr_working_sessions.user_id -> users.id
--   zr_episodic_logs.user_id -> users.id
--   zr_semantic_memories.user_id -> users.id OR NULL for global memory
--   zr_user_preferences.user_id -> users.id
--   zr_skill_memories.user_id -> users.id OR NULL for global skill
--   user_token_balance.user_id is the string form of users.id
--   token_consumption_log.user_id -> user_token_balance.user_id
--   token_consumption_log.task_id is the string form of search_tasks.id

-- Vector dimensions:
--   knowledge_chunks.embedding vector(1024)
--   zr_semantic_memories.embedding vector(1024)
--   every vector index must use HNSW.
-- Keyword retrieval:
--   knowledge_chunks.search_vector tsvector
--   keyword retrieval must use PostgreSQL tsvector + GIN index.

-- Logical delete boundary:
--   search_tasks.deleted_at IS NULL must be used for user-facing task/report/knowledge queries.
--   zr_episodic_logs.deleted_at IS NULL must be used for active episodic memory queries.
--   zr_semantic_memories.deleted_at IS NULL must be used for active semantic memory queries.

-- Source traceability boundary:
--   search_histories records actual executed source_sites and search_mode.
--   knowledge_chunks must reference original search history IDs through source_search_ids.
--   knowledge_chunks must not duplicate source URL/title details in metadata when search_histories can be used.

-- Skill memory loading boundary:
--   zr_skill_memories.title is the skill name.
--   zr_skill_memories.desc is the first-stage description loaded before full SOP.
--   zr_skill_memories.content is loaded only after a stage-one match.
--   zr_skill_memories.citation is loaded only when explanation or traceability is needed.

-- Token accounting boundary:
--   reports.token_usage stores task-level token usage details by stage.
--   memory manager subagent writes user_token_balance and token_consumption_log after every task ends.
--   user_token_balance.total_consumed is cumulative actual usage.
--   token_consumption_log.estimated_before records pre-task estimate, actual_consumed records final measured usage.
