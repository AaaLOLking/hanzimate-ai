import type { ToolActivity } from "./tool-client";

const labels: Record<string, string> = {
  hsk_lookup: "中文学习资料", web_search: "联网搜索", expert_answer: "深入解答",
};
const states: Record<string, string> = {
  running: "查询中", succeeded: "已返回", failed: "查询失败",
  unavailable: "暂不可用", no_results: "未找到", cancelled: "已取消",
};

export function ToolActivityPanel({ activity }: { activity: ToolActivity | null }) {
  if (!activity) return null;
  return <aside className="rounded-2xl border border-slate-200 bg-white/80 p-4 text-sm" aria-live="polite">
    <p className="font-medium">{labels[activity.name] ?? "工具查询"} · {states[activity.status] ?? activity.status}</p>
    <p className="mt-1 text-slate-600">{activity.message}</p>
    {activity.sources?.length > 0 && <details className="mt-2">
      <summary className="cursor-pointer">查看资料来源（{activity.sources.length}）</summary>
      <ul className="mt-2 space-y-2">{activity.sources.map((source, index) => <li key={index}>
        {source.url?.startsWith("https://") ? <a className="underline" href={source.url} target="_blank" rel="noreferrer">{source.title}</a> : <span>{source.title}</span>}
        {source.level && <span> · {source.level} · 项目课程 v2</span>}
        <p className="text-slate-600">{source.explanation ?? source.excerpt}</p>
      </li>)}</ul>
    </details>}
  </aside>;
}
