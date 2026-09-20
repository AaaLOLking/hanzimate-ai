# MVP 数据库 ERD

## 1. 设计原则

- 用户状态是证据事件的投影，不是不可解释的模型结论；
- 课程版本不可变，发布新版本不覆盖旧学习记录；
- 候选错误与确认后的长期错误分表；
- 复习日志不可变，FSRS 当前状态可以重建；
- 向量表必须使用 namespace 和 owner_id 隔离；
- 录音对象只保存引用、保留期限和 consent，不把二进制写入数据库。

## 2. 实体关系

~~~mermaid
erDiagram
    USERS ||--o{ CONSENTS : grants
    USERS ||--o{ LEARNER_MISSIONS : owns
    USERS ||--|| LEARNER_PROFILES : has
    USERS ||--o{ PROFILE_FACTS : has
    USERS ||--o{ WORKSPACES : opens
    WORKSPACES ||--o{ SESSIONS : contains
    SESSIONS ||--o{ UTTERANCES : records
    SESSIONS ||--o{ SESSION_EVENTS : observes
    SESSIONS ||--o| SESSION_SUMMARIES : produces
    SESSIONS ||--o{ ERROR_EVENTS : observes
    USERS ||--o{ ERROR_CLUSTERS : accumulates
    SESSION_SUMMARIES ||--o{ ERROR_EVENTS : proposes
    ERROR_CLUSTERS ||--o{ ERROR_EVENTS : groups
    ERROR_CLUSTERS ||--o| REVIEW_CARDS : schedules
    USERS ||--o| REVIEW_PREFERENCES : configures
    USERS ||--o{ REVIEW_REMINDERS : receives
    REVIEW_CARDS ||--o{ REVIEW_ATTEMPTS : retrieves
    REVIEW_ATTEMPTS ||--o| REVIEW_LOGS : rates
    REVIEW_CARDS ||--o{ REVIEW_LOGS : records
    COURSES ||--o{ COURSE_VERSIONS : publishes
    COURSE_VERSIONS ||--o{ LESSON_VERSIONS : contains
    USERS ||--o{ LESSON_PROGRESS : tracks
    WORKSPACES ||--o| LESSON_PROGRESS : resumes
    LESSON_VERSIONS ||--o{ LESSON_PROGRESS : receives
    LESSON_PROGRESS ||--o{ LEARNING_EVIDENCE : produces
    LESSON_VERSIONS ||--o{ LEARNING_EVIDENCE : identifies
    USERS ||--o{ LESSON_MESSAGES : owns
    LESSON_PROGRESS ||--o{ LESSON_MESSAGES : scopes
    KNOWLEDGE_SOURCES ||--o{ KNOWLEDGE_CITATIONS : supports
    KNOWLEDGE_PAGES ||--o{ KNOWLEDGE_CITATIONS : contains
    USERS ||--o{ EMBEDDINGS : owns
    USERS ||--o{ MODEL_RUNS : invokes

    USERS {
      uuid id PK
      text email UK
      text locale
      timestamptz created_at
      timestamptz deleted_at
    }

    LEARNER_PROFILES {
      uuid user_id PK,FK
      text support_language
      text estimated_hsk_band
      jsonb skill_estimates
      jsonb preferences
      int projection_version
      timestamptz updated_at
    }

    PROFILE_FACTS {
      uuid id PK
      uuid user_id FK
      text fact_type
      jsonb value
      text status
      numeric confidence
      uuid evidence_id
      timestamptz valid_from
      timestamptz expires_at
    }

    WORKSPACES {
      uuid id PK
      uuid user_id FK
      text kind
      text title
      text status
      jsonb state
      timestamptz last_opened_at
    }

    SESSIONS {
      uuid id PK
      uuid workspace_id FK
      text kind
      text correction_mode
      text model_id
      text skill_version
      timestamptz started_at
      timestamptz ended_at
    }

    UTTERANCES {
      uuid id PK
      uuid session_id FK
      int sequence_no
      text speaker
      text transcript
      numeric asr_confidence
      int started_ms
      int ended_ms
    }

    SESSION_SUMMARIES {
      uuid id PK
      uuid session_id FK,UK
      uuid user_id FK
      text task_status
      jsonb highlights
      text next_step
      text provider
      text model
      text skill_version
      timestamptz generated_at
    }

    SESSION_EVENTS {
      uuid id PK
      uuid session_id FK
      text client_event_id
      text event_type
      int elapsed_ms
      jsonb event_payload
      timestamptz created_at
    }

    ERROR_EVENTS {
      uuid id PK
      uuid session_id FK
      uuid user_id FK
      uuid summary_id FK
      uuid cluster_id FK
      text error_type
      text subtype
      text learner_text
      text corrected_text
      text explanation
      numeric confidence
      text status
      jsonb hsk_tags
      uuid evidence_utterance_id
      timestamptz observed_at
    }

    ERROR_CLUSTERS {
      uuid id PK
      uuid user_id FK
      text canonical_key
      text error_type
      text subtype
      text status
      int occurrence_count
      timestamptz first_seen_at
      timestamptz last_seen_at
    }

    REVIEW_CARDS {
      uuid id PK
      uuid user_id FK
      uuid error_cluster_id FK
      numeric difficulty
      numeric stability
      timestamptz due_at
      text state
      int lapses
    }

    REVIEW_LOGS {
      uuid id PK
      uuid review_card_id FK
      text rating
      numeric elapsed_days
      numeric scheduled_days
      jsonb response
      timestamptz reviewed_at
    }

    COURSES {
      uuid id PK
      text slug UK
      text status
      timestamptz created_at
    }

    COURSE_VERSIONS {
      uuid id PK
      uuid course_id FK
      int version
      text title
      text description
      text framework
      text level
      text status
      jsonb source_metadata
      timestamptz published_at
    }

    LESSON_VERSIONS {
      uuid id PK
      uuid course_version_id FK
      text slug
      int version
      int position
      text title
      text framework
      text level
      text objective
      int estimated_minutes
      jsonb targets
      jsonb sources
      jsonb content
      jsonb assessment_config
      text content_hash
      text status
      text skill_version
      timestamptz published_at
    }

    LESSON_PROGRESS {
      uuid id PK
      uuid user_id FK
      uuid lesson_version_id FK
      uuid workspace_id FK,UK
      text status
      int current_step
      int attempt_count
      numeric best_score
      timestamptz started_at
      timestamptz completed_at
      timestamptz updated_at
    }

    LEARNING_EVIDENCE {
      uuid id PK
      uuid user_id FK
      uuid lesson_progress_id FK
      uuid lesson_version_id FK
      text evidence_type
      text response
      boolean passed
      numeric score
      text feedback
      text answer_rule
      text skill_version
      timestamptz observed_at
    }

    LESSON_MESSAGES {
      uuid id PK
      uuid lesson_progress_id FK
      uuid user_id FK
      text role
      text content
      text provider
      text model
      jsonb citations
      timestamptz created_at
    }

    EMBEDDINGS {
      uuid id PK
      uuid owner_id
      text namespace
      text source_type
      uuid source_id
      vector embedding
      jsonb metadata
      timestamptz created_at
    }

    MODEL_RUNS {
      uuid id PK
      uuid user_id FK
      text provider
      text model
      text task
      int latency_ms
      int input_tokens
      int output_tokens
      numeric estimated_cost
      text status
      text error_code
      text fallback_from
      timestamptz created_at
    }

    ACCOUNT_DELETION_RECEIPTS {
      uuid id PK
      jsonb deleted_records
      timestamptz deleted_at
    }
~~~

## 3. 状态约束

### error_events.status

- candidate：模型提出但尚未确认；
- confirmed：用户或高可信规则确认；
- rejected：用户驳回；
- superseded：被更准确事件替代。

### error_clusters.status

- active：用户确认、可参与后续召回；
- archived：用户归档、不再参与召回。

当前 Week 5 直接使用 `error_events.cluster_id` 保留簇成员关系。未来如果需要一个事件属于多个语义簇，再迁移为独立关联表；MVP 不提前增加这层复杂度。

### workspaces.status

- active；
- processing；
- review_due；
- completed；
- archived。

### lesson_progress.status / current_step

- `in_progress`：`current_step` 为 0、1、2，分别对应引导练习、无提示检索和迁移任务；
- `completed`：迁移任务通过后写为 3，同时将关联 workspace 标记为 completed；
- 每次尝试都追加 `learning_evidence`，失败证据不会被成功尝试覆盖。

## 4. 必要索引

- workspaces(user_id, last_opened_at desc)；
- utterances(session_id, sequence_no) unique；
- session_events(session_id, client_event_id) unique；
- error_events(user_id, status, observed_at desc)；
- error_clusters(user_id, canonical_key) unique；
- review_cards(user_id, due_at) where state != suspended；
- course_versions(course_id, version) unique；
- lesson_versions(course_version_id, slug, version) unique；
- lesson_progress(user_id, lesson_version_id) unique；
- lesson_messages(lesson_progress_id, created_at)；
- embeddings 使用 HNSW，检索前强制 namespace + owner_id 过滤；
- model_runs(user_id, created_at)；
- model_runs(provider, status)。

## 5. 数据保留

Week 8 实际实现将 `REVIEW_CARDS` 的算法细节存入 `fsrs_state` JSON，独立保留 `algorithm_due_at` 与 `due_at`；新增 `revision` 防止并发重复自评。`REVIEW_ATTEMPTS` 保存不可覆盖的原作答和题目快照，`REVIEW_LOGS` 保存自评、前后状态、参数与日期。上述早期示意中的 difficulty/stability/state 现位于 JSON 内。完整约束见 [review-scheduling.md](../review-scheduling.md)。

- 原始录音：当前 MVP 不保存；未来开放前重新征得同意并增加对象存储删除流程；
- 转写：账户存续期内保留，用户可删除；
- rejected 错误：保留最小审计记录，不参与召回；
- 模型运行日志：不含完整输入，建议 90 天；
- consent 随账户删除；匿名删除回执只保留随机编号、时间和各类删除数量；
- 匿名化产品指标与身份映射分离。
