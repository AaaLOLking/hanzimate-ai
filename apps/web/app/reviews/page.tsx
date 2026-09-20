"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiRequest } from "@/lib/api";
import {
  ratingLabels, reviewDate, type ReviewAttempt, type ReviewDashboard,
  type ReviewPreferences, type ReviewRating, type ReviewReceipt,
} from "@/lib/reviews";
import styles from "./reviews.module.css";

const weekdays = ["一", "二", "三", "四", "五", "六", "日"];
const ratingNotes = {
  again: "没想起来 / 看了答案才会", hard: "想了很久才想起来",
  good: "独立想起，略有停顿", easy: "立即想起，也能换场景使用",
};

export default function ReviewsPage() {
  const [data, setData] = useState<ReviewDashboard | null>(null);
  const [preferences, setPreferences] = useState<ReviewPreferences | null>(null);
  const [response, setResponse] = useState("");
  const [attempt, setAttempt] = useState<ReviewAttempt | null>(null);
  const [receipt, setReceipt] = useState<ReviewReceipt | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const submission = useRef<{ key: string; id: string } | null>(null);

  const refresh = useCallback(async () => {
    const next = await apiRequest<ReviewDashboard>("/api/v1/reviews");
    setData(next);
    setAttempt(next.cards[0]?.pending_attempt ?? null);
    return next;
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiRequest<ReviewDashboard>("/api/v1/reviews")
      .then((next) => {
        if (cancelled) return;
        setData(next);
        setPreferences(next.preferences);
        setAttempt(next.cards[0]?.pending_attempt ?? null);
      })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, []);

  const current = data?.cards[0];
  const timezone = data?.preferences.timezone ?? "Asia/Shanghai";

  async function submitAnswer(event: React.FormEvent) {
    event.preventDefault();
    if (!current || !response.trim() || busy) return;
    setBusy(true);
    setError("");
    const key = `${current.id}:${current.revision}:${response.trim()}`;
    if (submission.current?.key !== key) submission.current = { key, id: crypto.randomUUID() };
    try {
      const saved = await apiRequest<ReviewAttempt>(`/api/v1/reviews/${current.id}/attempts`, {
        method: "POST", body: JSON.stringify({
          request_id: submission.current.id, card_revision: current.revision, response,
        }),
      });
      setAttempt(saved);
      setReceipt(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "作答保存失败，可重试或刷新恢复");
    } finally { setBusy(false); }
  }

  async function rate(rating: ReviewRating) {
    if (!attempt || busy) return;
    setBusy(true);
    setError("");
    try {
      const saved = await apiRequest<ReviewReceipt>(`/api/v1/review-attempts/${attempt.id}/rating`, {
        method: "POST", body: JSON.stringify({ rating }),
      });
      setReceipt(saved);
      setResponse("");
      submission.current = null;
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "自评保存失败，请重试");
    } finally { setBusy(false); }
  }

  async function savePreferences(event: React.FormEvent) {
    event.preventDefault();
    if (!preferences) return;
    setSaving(true);
    setNotice("");
    setError("");
    try {
      const saved = await apiRequest<ReviewPreferences>("/api/v1/review-preferences", {
        method: "PUT", body: JSON.stringify(preferences),
      });
      setPreferences(saved);
      setData((previous) => previous ? { ...previous, preferences: saved } : previous);
      setNotice("已保存。新节奏用于之后完成的复习；已到期内容仍可学习。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "设置保存失败");
    } finally { setSaving(false); }
  }

  async function dismiss() {
    if (!data?.reminder) return;
    try {
      await apiRequest(`/api/v1/review-reminders/${data.reminder.id}/dismiss`, { method: "PATCH" });
      setData({ ...data, reminder: null });
    } catch (err) { setError(err instanceof Error ? err.message : "提醒暂时无法关闭"); }
  }

  return (
    <AppShell
      active="reviews"
      panel={(
        <div className={styles.rhythm}>
          <span className="sectionLabel">YOUR RHYTHM</span><h2>按你的节奏</h2>
          <p>少量、持续，比一次刷完更重要。</p>
          {preferences ? <form onSubmit={savePreferences}>
            <label htmlFor="review-mode">复习间隔</label>
            <select id="review-mode" value={preferences.schedule_mode} onChange={(event) => setPreferences({ ...preferences, schedule_mode: event.target.value as "adaptive" | "fixed" })}>
              <option value="adaptive">按记忆情况自动安排</option><option value="fixed">我来指定间隔</option>
            </select>
            {preferences.schedule_mode === "fixed" ? <>
              <label htmlFor="review-interval">每隔几天（1–60 天）</label>
              <input id="review-interval" type="number" min={1} max={60} required value={preferences.fixed_interval_days}
                onChange={(event) => setPreferences({ ...preferences, fixed_interval_days: Number(event.target.value) })} />
              <small>选择“忘记了”时次日重练；其他自评使用此间隔，非学习日顺延。</small>
            </> : <>
              <label htmlFor="review-retention">复习密度</label>
              <select id="review-retention" value={preferences.desired_retention}
                onChange={(event) => setPreferences({ ...preferences, desired_retention: Number(event.target.value) })}>
                <option value={0.85}>轻量</option><option value={0.9}>均衡</option><option value={0.95}>更巩固</option>
              </select>
            </>}
            <fieldset><legend>可学习日</legend><div className={styles.days}>
              {weekdays.map((day, index) => <label key={day}>
                <input type="checkbox" checked={preferences.study_days.includes(index)}
                  onChange={(event) => setPreferences({ ...preferences, study_days: event.target.checked
                    ? [...preferences.study_days, index].sort() : preferences.study_days.filter((value) => value !== index) })} />
                <span>{day}</span>
              </label>)}
            </div></fieldset>
            <label htmlFor="review-timezone">所在时区</label>
            <input id="review-timezone" required maxLength={80} list="review-timezones" value={preferences.timezone}
              onChange={(event) => setPreferences({ ...preferences, timezone: event.target.value })} />
            <datalist id="review-timezones"><option value="Asia/Shanghai" /><option value="Asia/Tokyo" /><option value="Europe/London" /><option value="America/New_York" /></datalist>
            <label className={styles.checkLabel}><input type="checkbox" checked={preferences.reminder_enabled}
              onChange={(event) => setPreferences({ ...preferences, reminder_enabled: event.target.checked })} />开启站内提醒</label>
            <label htmlFor="review-time">提醒时间</label>
            <input id="review-time" type="time" required value={preferences.reminder_time}
              onChange={(event) => setPreferences({ ...preferences, reminder_time: event.target.value })} />
            <small>每天最多一次，只提醒到期内容。不是手机推送或邮件；后台服务运行时检查，进入网页后查看。</small>
            <button className="primaryButton" disabled={saving || preferences.study_days.length === 0}>
              {saving ? "正在保存…" : "保存复习设置"}
            </button>
            {!preferences.study_days.length ? <small role="alert">至少选择一个学习日。</small> : null}
            {notice ? <p className={styles.saved} role="status">{notice}</p> : null}
          </form> : null}
        </div>
      )}
      panelLabel="复习设置"
      sidebar={(
        <div className={styles.reviewPromo}>
          <span className="sectionLabel lightLabel">SPACED PRACTICE</span>
          <h1>学过，<br />也记得。</h1>
          <p>从你确认过的错误出发。先自己试一次，再看答案。</p>
          <div className={styles.stats}>
            <div><strong>{data?.due_count ?? "—"}</strong><span>现在可复习</span></div>
            <div><strong>{data?.reviewed_today ?? "—"}</strong><span>今天已复习</span></div>
          </div>
          <p className={styles.footnote}>复习次数不是掌握证明。下次能独立用出来，才是新的学习证据。</p>
        </div>
      )}
    >
      <div className={styles.reviewMain}>
        <header className={styles.header}>
          <div><span className="sectionLabel">YOUR REVIEW SESSION</span><h2>今日复习</h2></div>
          <button className="secondaryButton" disabled={busy} onClick={() => {
            setError("");
            void refresh().catch((err) => setError(err.message));
          }}>刷新列表</button>
        </header>
        {error ? <p className={styles.error} role="alert">{error}</p> : null}
        {data?.reminder && data.preferences.reminder_enabled ? (
          <div className={styles.reminder}>
            <p>到了你的复习时间，{data.reminder.due_count} 项旧知识在等你。</p>
            <button onClick={() => void dismiss()}>知道了</button>
          </div>
        ) : null}
        {receipt ? <div className={styles.success} role="status">
          <strong>这次复习已保存 · {ratingLabels[receipt.rating]}</strong>
          <span>本项下次安排：{reviewDate(receipt.due_at, timezone)}（{timezone}）</span>
        </div> : null}

        {!data ? <p>正在读取你的复习计划…</p> : current ? (
          <article className={styles.practice + " reveal"}>
            <div className={styles.practiceTop}><span>01 / 先回忆</span><span>来自已确认错误</span></div>
            <h2>{current.title}</h2>
            <p className={styles.prompt}>{attempt?.prompt ?? current.prompt}</p>
            {!attempt ? (
              <form onSubmit={submitAnswer}>
                <label htmlFor="review-answer">你的中文表达</label>
                <textarea id="review-answer" value={response} maxLength={2000} rows={5}
                  onChange={(event) => setResponse(event.target.value)} disabled={busy}
                  placeholder="不看答案先试一次；想不起来也可以写‘不会’。" />
                <div className={styles.submitRow}>
                  <small>提交前不会显示参考表达。</small>
                  <button className="primaryButton" disabled={busy || !response.trim()}>
                    {busy ? "正在保存…" : "提交并看反馈"}
                  </button>
                </div>
              </form>
            ) : (
              <div className={styles.feedback}>
                <span className="sectionLabel">02 / 对照与自评</span>
                <div><small>你的作答</small><p>{attempt.response}</p></div>
                <div className={styles.reference}><small>参考表达（不是唯一答案）</small>
                  <strong>{attempt.reference_answer}</strong><p>{attempt.explanation}</p></div>
                <p>{attempt.feedback}</p>
                <h3>看答案之前，你记得多少？</h3>
                <p className={styles.footnote}>请根据刚才的真实回忆情况选择；系统不会替你选择。</p>
                <div className={styles.ratings}>
                  {(Object.keys(ratingLabels) as ReviewRating[]).map((rating) => (
                    <button disabled={busy} key={rating} onClick={() => void rate(rating)}>
                      <strong>{ratingLabels[rating]}</strong><small>{ratingNotes[rating]}</small>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </article>
        ) : (
          <div className={styles.empty + " reveal"}>
            <span aria-hidden="true">✓</span>
            <h2>{data.active_count ? "目前没有到期复习" : "你的复习计划，从第一个错误开始"}</h2>
            <p>{data.active_count ? "不用提前刷题。可以继续课程，或把中文用在一次对话里。" : "完成对话后，在报告或错误本中确认一个错误，它就会出现在这里。"}</p>
            <Link className="primaryButton buttonLink" href={data.active_count ? "/courses" : "/errors"}>
              {data.active_count ? "继续学一课" : "查看错误本"}</Link>
          </div>
        )}

        {data?.upcoming.length ? <section className={styles.upcoming}>
          <span className="sectionLabel">COMING UP</span><h3>接下来的安排</h3>
          {data.upcoming.map((card) => <div key={card.id}>
            <strong>{card.title}</strong><span>{reviewDate(card.due_at, timezone)}</span>
          </div>)}
          <small>按 {timezone} 显示；非学习日会顺延。</small>
        </section> : null}
        {data?.history.length ? <details className={styles.history}>
          <summary>最近的复习记录（{data.history.length}）</summary>
          {data.history.map((log) => <p key={log.id}>
            {reviewDate(log.reviewed_at, timezone)} · {ratingLabels[log.rating]} → 下次 {reviewDate(log.due_at, timezone)}
          </p>)}
        </details> : null}
      </div>
    </AppShell>
  );
}
