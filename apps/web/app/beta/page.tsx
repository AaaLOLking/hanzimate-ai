"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiRequest, type BetaDashboard, type BetaFeedback } from "@/lib/api";

import styles from "./beta.module.css";

const milestoneCopy = {
  conversations: { label: "完成对话", href: "/", note: "在真实场景里开口练习" },
  lessons: { label: "完成课程", href: "/courses", note: "学完并通过课程练习" },
  reviews: { label: "完成复习", href: "/reviews", note: "回顾已确认的个人错误" },
  feedback: { label: "提交反馈", href: "#feedback-form", note: "告诉我们哪里值得保留或修正" },
} as const;

const areaLabels: Record<BetaFeedback["area"], string> = {
  conversation: "对话训练",
  course: "系统课程",
  review: "错误复习",
  overall: "整体体验",
};

const issueLabels: Record<BetaFeedback["issue_type"], string> = {
  praise: "做得好的地方",
  wrong_correction: "纠正不准确",
  confusing: "内容难理解",
  slow: "响应慢或卡住",
  bug: "功能不能用",
  idea: "功能建议",
  other: "其他",
};

type FeedbackDraft = {
  area: BetaFeedback["area"];
  issue_type: BetaFeedback["issue_type"];
  rating: number;
  is_blocking: boolean;
  message: string;
};

const emptyDraft: FeedbackDraft = {
  area: "overall",
  issue_type: "idea",
  rating: 4,
  is_blocking: false,
  message: "",
};

export default function BetaPage() {
  const [dashboard, setDashboard] = useState<BetaDashboard | null>(null);
  const [draft, setDraft] = useState<FeedbackDraft>(emptyDraft);
  const [status, setStatus] = useState<"loading" | "ready" | "sending" | "sent" | "error">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    void apiRequest<BetaDashboard>("/api/v1/beta")
      .then((result) => {
        setDashboard(result);
        setStatus("ready");
      })
      .catch((reason: Error) => {
        setError(reason.message);
        setStatus("error");
      });
  }, []);

  async function submitFeedback(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("sending");
    setError("");
    try {
      await apiRequest<BetaFeedback>("/api/v1/beta/feedback", {
        method: "POST",
        body: JSON.stringify(draft),
      });
      const refreshed = await apiRequest<BetaDashboard>("/api/v1/beta");
      setDashboard(refreshed);
      setDraft(emptyDraft);
      setStatus("sent");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "反馈暂时没有保存，请重试");
      setStatus("error");
    }
  }

  return (
    <AppShell active="beta">
      <section className={styles.hero}>
        <div>
          <p className={styles.kicker}>CLOSED BETA</p>
          <h1>一起把中文教练磨得更好</h1>
          <p>完成一轮真实学习，再告诉我们哪里好用、哪里需要修正。你的反馈只包含你主动填写的文字。</p>
        </div>
        <div className={dashboard?.ready_for_exit ? styles.readyBadge : styles.progressBadge}>
          <strong>{dashboard?.ready_for_exit ? "本轮已完成" : "体验进行中"}</strong>
          <span>{dashboard?.ready_for_exit ? "谢谢你完成完整学习闭环" : "完成四项即可结束本轮体验"}</span>
        </div>
      </section>

      <div className={styles.content}>
        {status === "loading" ? <p className={styles.notice} aria-live="polite">正在整理你的体验进度…</p> : null}
        {error ? <p className={`${styles.notice} ${styles.error}`} role="alert">{error}</p> : null}
        {status === "sent" ? <p className={`${styles.notice} ${styles.success}`} role="status">反馈已保存，谢谢你的直接意见。</p> : null}

        {dashboard ? (
          <section aria-labelledby="beta-progress-title" className={styles.progressSection + " reveal"}>
            <div className={styles.sectionHeading}>
              <div><p className={styles.kicker}>YOUR TEST JOURNEY</p><h2 id="beta-progress-title">本轮体验进度</h2></div>
              <span>目标：3 次对话 · 2 节课程 · 2 次复习 · 1 条反馈</span>
            </div>
            <div className={styles.progressGrid}>
              {(Object.keys(milestoneCopy) as Array<keyof typeof milestoneCopy>).map((key) => {
                const item = dashboard.progress[key];
                const copy = milestoneCopy[key];
                const width = Math.min(100, Math.round((item.current / item.target) * 100));
                return (
                  <article className={item.complete ? styles.completeCard : styles.progressCard} key={key}>
                    <div><span>{item.complete ? "✓" : `${item.current}/${item.target}`}</span><strong>{copy.label}</strong></div>
                    <p>{copy.note}</p>
                    <i aria-hidden="true"><b style={{ width: `${width}%` }} /></i>
                    <Link href={copy.href}>{item.complete ? "已完成" : "继续体验 →"}</Link>
                  </article>
                );
              })}
            </div>
          </section>
        ) : null}

        <div className={styles.mainGrid}>
          <section className={styles.formPanel + " reveal"} id="feedback-form">
            <p className={styles.kicker}>TELL US DIRECTLY</p>
            <h2>提交一条体验反馈</h2>
            <p className={styles.intro}>请不要粘贴护照、手机号、住址或整段私人对话。描述发生了什么、你原本希望看到什么，就足够我们定位问题。</p>

            <form onSubmit={submitFeedback}>
              <div className={styles.fieldRow}>
                <label>反馈位置<select onChange={(event) => setDraft({ ...draft, area: event.target.value as BetaFeedback["area"] })} value={draft.area}>
                  {Object.entries(areaLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select></label>
                <label>反馈类型<select onChange={(event) => setDraft({ ...draft, issue_type: event.target.value as BetaFeedback["issue_type"] })} value={draft.issue_type}>
                  {Object.entries(issueLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select></label>
              </div>

              <fieldset className={styles.rating}>
                <legend>这次体验几分？</legend>
                <div>{[1, 2, 3, 4, 5].map((score) => (
                  <label key={score}><input checked={draft.rating === score} name="rating" onChange={() => setDraft({ ...draft, rating: score })} type="radio" value={score} /><span>{score}</span></label>
                ))}</div>
                <small>1 分很糟 · 5 分很好</small>
              </fieldset>

              <label className={styles.messageField}>具体发生了什么？<textarea maxLength={1200} minLength={3} onChange={(event) => setDraft({ ...draft, message: event.target.value })} placeholder="例如：我说‘两瓶水’，AI 却纠正成了‘两个水’。我希望它解释为什么这里要用‘瓶’。" required rows={6} value={draft.message} /><small>{draft.message.length}/1200</small></label>

              <label className={styles.blocking}><input checked={draft.is_blocking} onChange={(event) => setDraft({ ...draft, is_blocking: event.target.checked })} type="checkbox" /><span><strong>这个问题让我无法继续学习</strong><small>只在页面卡住、内容无法提交或主流程中断时勾选</small></span></label>

              <button disabled={status === "sending" || draft.message.trim().length < 3} type="submit">{status === "sending" ? "正在保存…" : "提交反馈"}</button>
            </form>
          </section>

          <aside className={styles.historyPanel + " reveal"}>
            <p className={styles.kicker}>YOUR FEEDBACK</p>
            <h2>我提交的反馈</h2>
            {dashboard?.feedback.length ? <ul>{dashboard.feedback.map((item) => (
              <li key={item.id}>
                <div><span>{areaLabels[item.area]}</span><time dateTime={item.created_at}>{new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(new Date(item.created_at))}</time></div>
                <strong>{issueLabels[item.issue_type]} · {item.rating}/5</strong>
                <p>{item.message}</p>
                <small>{item.is_blocking ? "阻断问题 · 已记录" : "已记录"}</small>
              </li>
            ))}</ul> : <div className={styles.emptyHistory}><span>✦</span><p>还没有反馈。好用的地方也值得告诉我们，它会决定下一阶段保留什么。</p></div>}
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
