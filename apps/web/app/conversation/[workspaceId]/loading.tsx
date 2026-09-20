export default function ConversationLoading() {
  return (
    <main className="conversationLoading" id="main-content" tabIndex={-1}>
      <span className="loadingPulse" />
      <p>正在恢复对话工作区…</p>
    </main>
  );
}
