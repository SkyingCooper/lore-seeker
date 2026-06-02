-- Lore Seeker DB table contract snapshot.
-- Source of truth remains backend/db/schema.sql.
-- This file defines table names, ownership, and cross-table constraints expected by Agents.

-- Core business chain:
-- users -> topics -> search_tasks -> reports -> knowledge_chunks

-- Agent memory tables use the zr_ prefix.
-- Required tables:
--   zr_working_sessions
--   zr_episodic_logs
--   zr_semantic_memories
--   zr_user_preferences
--   zr_skill_memories

-- Required ownership constraints:
--   topics.user_id -> users.id
--   search_tasks.user_id -> users.id
--   search_tasks.topic_id -> topics.id
--   reports.task_id -> search_tasks.id
--   knowledge_chunks.report_id -> reports.id
--   search_histories.user_id -> users.id
--   search_histories.task_id -> search_tasks.id
--   search_histories.parent_id -> search_histories.id for subtask-level histories
--   zr_working_sessions.user_id -> users.id
--   zr_episodic_logs.user_id -> users.id
--   zr_semantic_memories.user_id -> users.id OR NULL for global memory
--   zr_user_preferences.user_id -> users.id
--   zr_skill_memories.user_id -> users.id OR NULL for global skill

-- Vector dimensions:
--   knowledge_chunks.embedding vector(1536)
--   zr_semantic_memories.embedding vector(1536)

-- Logical delete boundary:
--   search_tasks.deleted_at IS NULL must be used for user-facing task/report/knowledge queries.
