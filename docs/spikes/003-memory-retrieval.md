# Spike 003：PostgreSQL + pgvector 记忆召回

## 目的

验证混合检索可以在不跨用户、不注入全部历史的前提下，选出当前任务最相关的学习证据。

## 当前实现与阶段决策（2026-08-24）

Week 5 先交付可审计的结构化基线，而不是直接引入向量数据库：确认后的 `ErrorEvent` 按 `user_id + canonical_key` 聚合为 `ErrorCluster`，新会话只查询本用户 `active` 状态、按最近出现排序的前 5 条。驳回事件永不聚合，归档簇立即停止召回。

这样能先验证“候选 → 人工确认 → 聚合 → 召回 → 删除”的产品语义和权限边界。pgvector 仍用于下一阶段的语义扩展召回与公共课程知识检索，但不能代替结构化状态、canonical key、owner 过滤或删除语义。本页下面的 Recall@5、Precision@5 和 200 ms 门槛尚未完成，不能用当前规则基线冒充向量检索验收。

## 数据

- 3 个虚拟用户；
- 每人 30 条错误证据、20 条会话摘要；
- 12 节公共课程；
- 中文原文与英文辅助说明混合；
- 至少 10 组语义相近但用户不同的干扰项。

## Namespace

- user:{user_id}:errors；
- user:{user_id}:summaries；
- public:course-pages；
- public:reference-pages。

所有用户 namespace 查询必须同时使用 owner_id 过滤。不得先全局向量召回后再在应用层删除其他用户结果。

## 混合召回

1. 结构化过滤：用户、状态、框架、级别、错误类型；
2. 向量召回 Top 20；
3. canonical key 与最近出现加权；
4. 可选 rerank；
5. 输出最多 5 条记忆和来源；
6. Context Pack 做 Token 上限检查。

## 场景

- 食堂点餐召回量词错误；
- 医院挂号不召回无关的把字句；
- HSK 语法课召回已确认的同类错误；
- rejected 或 muted 记忆永不召回；
- 用户 A 的相似错误不能出现在用户 B；
- 删除记忆后索引不可继续命中。

## 指标

- Recall@5；
- Precision@5；
- mean reciprocal rank；
- cross-user leakage count；
- rejected/muted leakage count；
- p50/p95 retrieval latency；
- Context Pack Token 数。

## 通过标准

- cross-user leakage = 0；
- rejected/muted leakage = 0；
- 目标测试集 Recall@5 ≥ 90%；
- Precision@5 ≥ 80%；
- p95 ≤ 200 ms；
- 单次注入最多 5 条用户记忆；
- 每个结果都能返回 source_id、证据和置信度。
