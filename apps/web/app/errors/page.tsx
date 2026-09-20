"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  apiRequest,
  type ErrorCluster,
  type ErrorEvent,
} from "@/lib/api";
import { type ReviewDashboard, reviewDate } from "@/lib/reviews";

type ErrorBookView = "date" | "clusters";

export default function ErrorBookPage() {
  const [clusters, setClusters] = useState<ErrorCluster[]>([]);
  const [candidates, setCandidates] = useState<ErrorEvent[]>([]);
  const [confirmedEvents, setConfirmedEvents] = useState<ErrorEvent[]>([]);
  const [view, setView] = useState<ErrorBookView>("date");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [workingId, setWorkingId] = useState<string | null>(null);
  const [reviews, setReviews] = useState<ReviewDashboard | null>(null);
  const [editing, setEditing] = useState<{ id: string; example: string; explanation: string } | null>(null);

  async function loadMemory() {
    setError("");
    try {
      const [nextClusters, nextCandidates, nextConfirmed, nextReviews] = await Promise.all([
        apiRequest<ErrorCluster[]>("/api/v1/error-clusters"),
        apiRequest<ErrorEvent[]>("/api/v1/errors?status=candidate"),
        apiRequest<ErrorEvent[]>("/api/v1/errors?status=confirmed"),
        apiRequest<ReviewDashboard>("/api/v1/reviews"),
      ]);
      setClusters(nextClusters);
      setCandidates(nextCandidates);
      setConfirmedEvents(nextConfirmed);
      setReviews(nextReviews);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "错误本加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiRequest<ErrorCluster[]>("/api/v1/error-clusters"),
      apiRequest<ErrorEvent[]>("/api/v1/errors?status=candidate"),
      apiRequest<ErrorEvent[]>("/api/v1/errors?status=confirmed"),
      apiRequest<ReviewDashboard>("/api/v1/reviews"),
    ])
      .then(([nextClusters, nextCandidates, nextConfirmed, nextReviews]) => {
        if (cancelled) return;
        setClusters(nextClusters);
        setCandidates(nextCandidates);
        setConfirmedEvents(nextConfirmed);
        setReviews(nextReviews);
      })
      .catch((requestError) => {
        if (cancelled) return;
        setError(requestError instanceof Error ? requestError.message : "错误本加载失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function decide(candidate: ErrorEvent, status: "confirmed" | "rejected") {
    setWorkingId(candidate.id);
    try {
      await apiRequest<ErrorEvent>(`/api/v1/errors/${candidate.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await loadMemory();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "判断保存失败");
    } finally {
      setWorkingId(null);
    }
  }

  async function archive(cluster: ErrorCluster) {
    setWorkingId(cluster.id);
    try {
      await apiRequest<void>(`/api/v1/error-clusters/${cluster.id}`, { method: "DELETE" });
      setClusters((current) => current.filter((item) => item.id !== cluster.id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "归档失败");
    } finally {
      setWorkingId(null);
    }
  }

  async function saveCluster(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    setWorkingId(editing.id);
    try {
      const updated = await apiRequest<ErrorCluster>(`/api/v1/error-clusters/${editing.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          corrected_example: editing.example,
          explanation: editing.explanation,
        }),
      });
      setClusters((current) => current.map((item) => item.id === updated.id ? updated : item));
      setEditing(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "记忆修改失败");
    } finally {
      setWorkingId(null);
    }
  }

  const dateGroups = useMemo(() => {
    const groups = new Map<string, ErrorEvent[]>();
    for (const event of [...candidates, ...confirmedEvents]) {
      const key = new Date(event.observed_at).toDateString();
      const list = groups.get(key);
      if (list) list.push(event);
      else groups.set(key, [event]);
    }
    return [...groups.entries()].sort(
      (first, second) => new Date(second[0]).getTime() - new Date(first[0]).getTime(),
    );
  }, [candidates, confirmedEvents]);

  function clusterLabel(event: ErrorEvent): string {
    const cluster = clusters.find((item) => item.id === event.cluster_id);
    return cluster ? cluster.corrected_example : event.subtype;
  }

  const dateGroupLabel = (key: string) =>
    new Date(key).toLocaleDateString("zh-CN", {
      day: "numeric",
      month: "long",
      weekday: "short",
      year: "numeric",
    });

  return (
    <AppShell active="errors">
      <section className="errorBookHero">
        <span className="sectionLabel">LONG-TERM LEARNING MEMORY</span>
        <h1>错误本</h1>
        <p>确认后会自动加入复习计划。归档后，它不会再参与新对话或复习提醒。</p>
        <Link className="primaryButton buttonLink" href="/reviews">进入今日复习 →</Link>
        <div className="memoryStats">
          <div><strong>{clusters.length}</strong><span>活跃错误模式</span></div>
          <div><strong>{candidates.length}</strong><span>待确认候选</span></div>
        </div>
      </section>

      <section className="errorBookContent">
        {error ? <p className="reportError" role="alert">{error}</p> : null}
        {loading ? <p className="memoryEmpty">正在读取你的学习记忆…</p> : null}

        {!loading ? (
          <div className="viewToggle" role="group" aria-label="错误本视图">
            <button aria-pressed={view === "date"} className={view === "date" ? "active" : ""} onClick={() => setView("date")} type="button">按日期</button>
            <button aria-pressed={view === "clusters"} className={view === "clusters" ? "active" : ""} onClick={() => setView("clusters")} type="button">按聚类</button>
          </div>
        ) : null}

        {!loading && view === "date" ? (
          dateGroups.length ? (
            <div className="dateGroups">
              {dateGroups.map(([day, events]) => (
                <section className="dateGroup reveal" key={day}>
                  <header className="dateGroupHeader">
                    <h2>{dateGroupLabel(day)}</h2>
                    <span>{events.length} 条记录</span>
                  </header>
                  <div className="memoryGrid">
                    {events.map((event) => (
                      <article className={`memoryCard panelCard ${event.status === "candidate" ? "candidate" : ""}`} key={event.id}>
                        <div className="memoryCardTop">
                          <span className="memoryTag">{event.hsk_tags.join(" · ") || event.subtype}</span>
                          <span className={`dateStatus ${event.status}`}>{event.status === "candidate" ? "待确认" : "已确认"}</span>
                        </div>
                        <p className="memoryRewrite"><del>{event.learner_text}</del><strong>{event.corrected_text}</strong></p>
                        <p>{event.explanation}</p>
                        <small>所属记忆：{clusterLabel(event)}</small>
                        {event.status === "candidate" ? (
                          <div className="errorDecisionActions">
                            <button disabled={workingId === event.id} onClick={() => void decide(event, "confirmed")}>确认并记住</button>
                            <button disabled={workingId === event.id} onClick={() => void decide(event, "rejected")}>这不是错误</button>
                          </div>
                        ) : null}
                      </article>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          ) : (
            <div className="memoryEmpty">
              <strong>还没有学习错误记录</strong>
              <p>完成一次对话并回顾报告中的候选错误后，它会按日期出现在这里。</p>
              <Link className="primaryButton buttonLink" href="/practice">开始一次对话</Link>
            </div>
          )
        ) : null}

        {!loading && view === "clusters" && candidates.length ? (
          <div className="memorySection reveal">
            <div className="memorySectionHeading">
              <div><span className="sectionLabel">REQUIRES YOUR DECISION</span><h2>待确认</h2></div>
              <p>AI 不会自行把这些内容写入长期画像。</p>
            </div>
            <div className="memoryGrid">
              {candidates.map((candidate) => (
                <article className="memoryCard candidate panelCard panelCard--interactive" key={candidate.id}>
                  <span className="memoryTag">{candidate.hsk_tags.join(" · ") || candidate.subtype}</span>
                  <p className="memoryRewrite"><del>{candidate.learner_text}</del><strong>{candidate.corrected_text}</strong></p>
                  <p>{candidate.explanation}</p>
                  <div className="errorDecisionActions">
                    <button disabled={workingId === candidate.id} onClick={() => void decide(candidate, "confirmed")}>确认并记住</button>
                    <button disabled={workingId === candidate.id} onClick={() => void decide(candidate, "rejected")}>这不是错误</button>
                  </div>
                </article>
              ))}
            </div>
          </div>
        ) : null}

        {!loading && view === "clusters" ? (
          <div className="memorySection reveal">
            <div className="memorySectionHeading">
              <div><span className="sectionLabel">CONFIRMED PATTERNS</span><h2>已确认记忆</h2></div>
              <p>按最近出现时间召回，最多注入 5 个模式。</p>
            </div>
            {clusters.length ? (
              <div className="memoryGrid">
                {clusters.map((cluster) => (
                  <article className="memoryCard panelCard panelCard--interactive" key={cluster.id}>
                    <div className="memoryCardTop">
                      <span className="memoryTag">{cluster.error_type} · {cluster.subtype}</span>
                      <span>出现 {cluster.occurrence_count} 次</span>
                    </div>
                    {editing?.id === cluster.id ? (
                      <form className="memoryEditForm" onSubmit={saveCluster}>
                        <label htmlFor={`example-${cluster.id}`}>你想记住的正确说法</label>
                        <input id={`example-${cluster.id}`} maxLength={1000} onChange={(event) => setEditing({ ...editing, example: event.target.value })} required value={editing.example} />
                        <label htmlFor={`explanation-${cluster.id}`}>给自己的解释</label>
                        <textarea id={`explanation-${cluster.id}`} maxLength={1000} onChange={(event) => setEditing({ ...editing, explanation: event.target.value })} required rows={3} value={editing.explanation} />
                        <div><button disabled={workingId === cluster.id}>保存修改</button><button onClick={() => setEditing(null)} type="button">取消</button></div>
                      </form>
                    ) : (
                      <>
                        <strong className="correctedExample">{cluster.corrected_example}</strong>
                        <p>{cluster.explanation}</p>
                      </>
                    )}
                    <small>最近确认 {new Date(cluster.last_seen_at).toLocaleDateString("zh-CN")}</small>
                    {cluster.next_review_at && reviews ? <small>复习安排：{reviewDate(cluster.next_review_at, reviews.preferences.timezone)}</small> : null}
                    {editing?.id !== cluster.id ? <div className="memoryCardActions"><button className="editMemory" disabled={workingId === cluster.id} onClick={() => setEditing({ id: cluster.id, example: cluster.corrected_example, explanation: cluster.explanation })}>修改</button><button className="archiveMemory" disabled={workingId === cluster.id} onClick={() => void archive(cluster)}>归档，不再召回</button></div> : null}
                  </article>
                ))}
              </div>
            ) : (
              <div className="memoryEmpty">
                <strong>还没有已确认的错误</strong>
                <p>完成一次对话并确认报告中的错误后，它会出现在这里。</p>
                <Link className="primaryButton buttonLink" href="/">开始一次对话</Link>
              </div>
            )}
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}
