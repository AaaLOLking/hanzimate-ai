# 连续会话验收记录（开发中）

日期：2026-09-17

## 本次实现

- 逻辑会话持续保存；continuous 模式不因八分钟到期结束，失联90秒仍进入结束保存阶段。
- 续接前等待输入、输出和工具空闲，排空保存请求；获取历史期间如收到新事件则放弃本次切换并重试。停止回答态也允许续接。
- 实际切换时暂时关闭麦克风音轨，界面提示稍候说话；建立完成按最新用户静音选择恢复。连接中的结束操作等待 offer 定下连接编号，再结束保存。
- 服务端生成最多12000字符的署名摘录，最近12条消息加早期用户摘录；保留最早锚点，按完整行筛选，旧AI回答不作已验证事实。
- Markdown导出按连接编号组织、标识播放状态并转义用户内容。
- 结束请求只包含尚未持久化或状态不一致的条目，完整旧记录留在数据库，避免长对话重复提交全部ID超出清单预算。
- 自动续接写入 segment_continued 事件；界面段号仍代表连接编号，包括异常重连。

## 验证（2026-09-17 最终全量）

- 后端全量 `uv run --project apps/api pytest apps/api/tests`：94 passed。
- `uv run --project apps/api ruff check apps/api`：All checks passed。
- `uv run alembic check`（apps/api 下）：No new upgrade operations detected。
- 前端 `pnpm lint:web`、`pnpm typecheck:web` 退出码 0；`pnpm build:web` 成功（10 个路由，含 /conversation/[workspaceId] 动态路由）。
- 新增8项后端用例已通过：连续/旧会话到期与失联、1500秒保存及旧480秒行为、三次恢复保留早期预算和目标、导出所有权和特殊字符、记忆上界/归属/不可靠转写排除，以及1200条旧记录无需完整结束清单仍成功保存。
- 浏览器 probe（隔离后端8001：临时SQLite、假SDP、无外部收费调用；Playwright 合成音轨与假 RTCPeerConnection，page.route 将 8000 转到 8001）。四个场景全部通过、页面 0 error：
  1. 三段续接：界面显示「连续对话 · 第 3 段」，连接 epoch 递增至 3，总时长9秒（隔离段长4秒 × 3 段），最终状态 completed。
  2. 早期记忆预算：第3段 session.update 指令包含早期锚点「我的租房预算是三千元」，署名摘录跨段保留；transcript.md 导出 HTTP 200 且含该早期转写。
  3. 静音保持：第1段用户静音后，跨两次自动续接全部音轨仍 enabled=false，即按最新静音选择恢复。
  4. 续接切换进行中结束：把下一次切换的 offer 人为延迟3秒，在「正在载入历史摘录并续接下一段」期间点击「结束并保存」；结束流程等待在途连接落定（epoch=2）后完成保存，最终状态 completed，无迟到 active 请求复活会话，导出 200。
- probe 脚本：apps/web/features/live/continuous-browser-probe.cjs 与 continuous-browser-probe-end-during-rollover.cjs。

## 实际限制

- 这是有损的确定性摘录，不是语义摘要；不存在无限上下文或保证记住所有事实的承诺。当前没有全历史按需检索工具。
- 续接暂时停麦，提示期间说话不会传入模型；当前尚未实现双连接预热或音频缓冲回放。
- 到期时若一直说话，续接会推迟；按墙钟时间触发是应用策略，不是精确读取供应商音频历史用量。
- 浏览器 probe 使用合成音轨与假 Peer，只验证流程、事件与状态机；不代表真人听感。三次恢复是API层与浏览器模拟，真实音频跨段、声学尾音和打断延迟仍需真人复验。
- 真实供应商工具调用未验收：探测返回 403 AllocationQuota.FreeTierOnly（免费额度耗尽/限制），详见工具验收记录；本记录不宣称真实联网搜索或真实模型问答已通过。
