# 连续会话检查点

阶段：全部验收完成，待主空间核验（2026-09-17）。

已核实：真实页面+8000后端文字流程已验证（自定义目标开始、输入、刷新恢复、结束保存、Markdown下载，无页面错误）。测试工作区5ca0a820-bec7-41e2-bfef-1f0beb07f5a2已结束。

浏览器 probe（隔离8001 + Playwright 合成音轨/假 RTCPeerConnection，非真人听感）四场景全部通过，页面 0 error：
1. 三段续接：「连续对话 · 第 3 段」，epoch=3，时长9秒（段长4秒 ×3），completed。
2. 早期记忆预算：第3段 session.update 指令含早期锚点「三千元」，transcript.md 导出 200 且含该转写。
3. 静音保持：第1段静音后跨两次续接全部音轨仍 enabled=false。
4. 续接切换进行中结束：切换 offer 延迟3秒期间点击「结束并保存」，等待连接落定（epoch=2）后 completed，无迟到 active 请求。
probe 脚本：continuous-browser-probe.cjs、continuous-browser-probe-end-during-rollover.cjs；runner 为 %TEMP%/hanzimate-probe-runner.cjs（eval 函数文件 + 全局 playwright 1.62）。

最终统一验证（本轮唯一执行者）：
- uv run --project apps/api pytest apps/api/tests：94 passed（旧基线92，工具侧新增2项）。
- uv run --project apps/api ruff check apps/api：All checks passed（修了 probe server 一处 import 排序）。
- uv run alembic check（apps/api）：No new upgrade operations detected。
- pnpm lint:web：0 warning。pnpm typecheck:web：0 错误。pnpm build:web：成功，10 路由；build 前停 3000 dev（旧PID27556），build 后重启（新PID65972，HTTP 200）。

交付文档：docs/architecture/continuous-memory-validation.md 已更新为最终实测数字（94项、四场景 probe 证据），保留并扩充「实际限制」诚实声明（合成音轨不代表真人听感；真实供应商工具 403 未验收）。

服务：3000开发PID65972、8000后端PID45112、隔离8001 PID61260（临时SQLite、假SDP、无外部收费调用）。

遗留（不宣称完成）：真人语音跨段听感/打断延迟/声学尾音；真实 DashScope 工具调用（403 FreeTierOnly，待用户处理额度）；真实联网搜索与 DeepSeek 问答；打断专项优化（用户已选择暂缓）。
