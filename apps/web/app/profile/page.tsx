"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  apiRequest,
  downloadAccountArchive,
  type AccountDeletionReceipt,
  type AccountOverview,
  type ModelRun,
} from "@/lib/api";

import styles from "./profile.module.css";

const scoreLabels: Record<string, string> = {
  listening: "听力",
  speaking: "口语",
  reading: "阅读",
  writing: "书写",
};

const taskLabels: Record<string, string> = {
  conversation_summary: "对话总结",
  lesson_tutor: "课程答疑",
};

const statusLabels: Record<string, string> = {
  succeeded: "完成",
  failed: "未完成",
  blocked: "已保护",
};

function ModelRunRow({ run }: { run: ModelRun }) {
  const source = run.provider === "local" ? "本机规则" : run.provider;
  return (
    <li>
      <span className={`${styles.runStatus} ${styles[run.status]}`}>{statusLabels[run.status]}</span>
      <span>
        <strong>{taskLabels[run.task] ?? run.task}</strong>
        <small>AI 生成 · {source}{run.fallback_from ? ` · 已从 ${run.fallback_from} 降级` : ""}</small>
      </span>
      <time dateTime={run.created_at}>
        {new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(new Date(run.created_at))}
      </time>
    </li>
  );
}

export default function ProfilePage() {
  const [overview, setOverview] = useState<AccountOverview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"export" | "delete" | "">("");
  const [email, setEmail] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [receipt, setReceipt] = useState<AccountDeletionReceipt | null>(null);

  useEffect(() => {
    void apiRequest<AccountOverview>("/api/v1/account")
      .then(setOverview)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  async function exportData() {
    setBusy("export");
    setError("");
    try {
      const archive = await downloadAccountArchive();
      const url = URL.createObjectURL(archive.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = archive.filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "数据导出失败");
    } finally {
      setBusy("");
    }
  }

  async function deleteData(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!overview) return;
    setBusy("delete");
    setError("");
    try {
      const deleted = await apiRequest<AccountDeletionReceipt>("/api/v1/account", {
        method: "DELETE",
        body: JSON.stringify({ email, confirmation }),
      });
      setReceipt(deleted);
      setOverview(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "账户删除失败");
    } finally {
      setBusy("");
    }
  }

  if (receipt) {
    return (
      <main className={styles.deletedShell} id="main-content" tabIndex={-1}>
        <section className={styles.deletedCard}>
          <span aria-hidden="true">✓</span>
          <p className={styles.kicker}>删除完成</p>
          <h1>你的学习数据已清除</h1>
          <p>删除回执：{receipt.receipt_id}</p>
          <p>本页不会继续请求账户数据。开发版刷新后会建立一个全新的空白演示账户。</p>
          <Link href="/onboarding">重新开始</Link>
        </section>
      </main>
    );
  }

  return (
    <AppShell active="profile">
      <section className={styles.hero}>
        <p className={styles.kicker}>LEARNING PROFILE</p>
        <h1>学习档案与数据</h1>
        <p>这里记录你的学习目标、长期错误记忆和 AI 使用情况。你可以随时带走或删除自己的数据。</p>
      </section>

      {error ? <p className={styles.error} role="alert">{error}</p> : null}
      {!overview && !error ? <p className={styles.loading} aria-live="polite">正在整理你的学习档案…</p> : null}

      {overview ? (
        <div className={styles.content}>
          <section className={styles.identityCard + " reveal"}>
            <div className={styles.avatar} aria-hidden="true">{overview.user.display_name.slice(0, 2).toUpperCase()}</div>
            <div>
              <p className={styles.kicker}>学习者</p>
              <h2>{overview.user.display_name}</h2>
              <p>{overview.user.email} · {overview.profile?.estimated_hsk_band ?? "尚未估级"}</p>
            </div>
            <Link href="/onboarding">修改学习设置</Link>
          </section>

          <section className={styles.stats + " reveal"} aria-label="学习记录概览">
            <article><strong>{overview.stats.conversations}</strong><span>次对话</span></article>
            <article><strong>{overview.stats.lessons_completed}/{overview.stats.lessons_started}</strong><span>完成课程</span></article>
            <article><strong>{overview.stats.active_memories}</strong><span>条长期记忆</span></article>
            <article><strong>{overview.stats.review_attempts}</strong><span>次复习作答</span></article>
          </section>

          <div className={styles.twoColumns}>
            <section className={styles.panel + " reveal"}>
              <p className={styles.kicker}>你的方向</p>
              <h2>{overview.mission?.success_looks_like[0] ?? "还没有设定学习目标"}</h2>
              <p className={styles.bodyCopy}>{overview.mission?.why ?? "完成首次建档后，这里会显示你的中文学习方向。"}</p>
              <dl className={styles.definitionList}>
                <div><dt>每周时间</dt><dd>{overview.mission?.weekly_minutes ?? 0} 分钟</dd></div>
                <div><dt>辅助语言</dt><dd>{overview.profile?.support_language ?? "未设置"}</dd></div>
                <div><dt>目标日期</dt><dd>{overview.mission?.deadline ?? "不设期限"}</dd></div>
              </dl>
              {overview.profile ? (
                <div className={styles.skillScores}>
                  {Object.entries(scoreLabels).map(([key, label]) => {
                    const score = overview.profile?.skill_estimates[key] ?? 0;
                    return <div key={key}><span>{label}</span><i><b style={{ width: `${score * 20}%` }} /></i><strong>{score}/5</strong></div>;
                  })}
                </div>
              ) : null}
            </section>

            <section className={styles.panel + " reveal"}>
              <p className={styles.kicker}>记忆边界</p>
              <h2>你决定 AI 记住什么</h2>
              <ul className={styles.policyList}>
                <li><span>长期学习记忆</span><strong>{overview.consent?.learning_memory ? "已开启" : "未开启"}</strong></li>
                <li><span>原始录音保存</span><strong>{overview.consent?.audio_retention ? "已同意；MVP 仍未保存" : "默认不保存"}</strong></li>
                <li><span>待确认错误</span><strong>不会自动写入长期记忆</strong></li>
              </ul>
              <p className={styles.bodyCopy}>你确认后的错误才会用于后续课程和复习。可以在错误本中修改或归档任何一条记忆。</p>
              <Link className={styles.inlineLink} href="/errors">管理 AI 记忆 →</Link>
            </section>
          </div>

          <section className={styles.usagePanel + " reveal"}>
            <div className={styles.usageIntro}>
              <p className={styles.kicker}>AI 使用保护</p>
              <h2>今天的模型调用</h2>
              <p>达到上限或服务失败时，课程答疑和对话总结会自动切到本机规则，学习不会中断。</p>
            </div>
            <div className={styles.usageNumbers}>
              <article><strong>{overview.model_usage.external_calls}</strong><span>外部调用</span></article>
              <article><strong>{overview.model_usage.remaining_external_calls}</strong><span>今日剩余</span></article>
              <article><strong>{overview.model_usage.failed_calls + overview.model_usage.blocked_calls}</strong><span>失败或保护</span></article>
            </div>
            <div className={styles.costNote}>
              {overview.model_usage.pricing_configured
                ? `今日估算费用 ¥${overview.model_usage.estimated_cost_yuan.toFixed(4)}`
                : "尚未配置价格，因此不展示可能误导的费用数字；每日调用次数保护已经生效。"}
            </div>
            {overview.model_usage.recent_runs.length ? (
              <ul className={styles.runList} aria-label="最近的 AI 使用记录">
                {overview.model_usage.recent_runs.map((run) => <ModelRunRow key={run.id} run={run} />)}
              </ul>
            ) : <p className={styles.emptyRuns}>今天还没有课程答疑或对话总结。</p>}
          </section>

          <section className={styles.dataPanel + " reveal"}>
            <div>
              <p className={styles.kicker}>你的数据</p>
              <h2>带走，或者清除</h2>
              <p>导出文件包含账户、学习目标、课程进度、对话文字、错误记忆和复习记录；不会包含密钥、原始录音或课程内部答案规则。</p>
            </div>
            <button className={styles.exportButton} disabled={busy !== ""} onClick={() => void exportData()}>
              {busy === "export" ? "正在整理…" : "下载我的数据"}
            </button>
            <details className={styles.dangerZone}>
              <summary>删除账户和全部学习数据</summary>
              <p>此操作不能撤销。为避免误触，请输入当前邮箱和“删除我的账户”。</p>
              <form onSubmit={deleteData}>
                <label htmlFor="delete-email">当前邮箱</label>
                <input id="delete-email" onChange={(event) => setEmail(event.target.value)} required type="email" value={email} />
                <label htmlFor="delete-confirmation">确认语</label>
                <input id="delete-confirmation" onChange={(event) => setConfirmation(event.target.value)} placeholder="删除我的账户" required value={confirmation} />
                <button
                  disabled={busy !== "" || email.trim().toLowerCase() !== overview.user.email.toLowerCase() || confirmation !== "删除我的账户"}
                >
                  {busy === "delete" ? "正在删除…" : "永久删除账户"}
                </button>
              </form>
            </details>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
