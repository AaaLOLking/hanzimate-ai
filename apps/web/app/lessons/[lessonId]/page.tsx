"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  apiRequest,
  type LessonActivity,
  type LessonAttemptResult,
  type LessonDetail,
  type LessonMessage,
} from "@/lib/api";

const stepMeta = [
  { key: "guided", label: "引导产出", note: "可以查看课内知识" },
  { key: "retrieval", label: "无提示提取", note: "先作答，再看提示" },
  { key: "transfer", label: "真实迁移", note: "换一个场景使用" },
] as const;

export default function LessonPage() {
  const params = useParams<{ lessonId: string }>();
  const lessonId = params.lessonId;
  const [lesson, setLesson] = useState<LessonDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const [response, setResponse] = useState("");
  const [attempting, setAttempting] = useState(false);
  const [attemptResult, setAttemptResult] = useState<LessonAttemptResult | null>(null);
  const [showKnowledge, setShowKnowledge] = useState(false);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiRequest<LessonDetail>(`/api/v1/lessons/${lessonId}`)
      .then((detail) => {
        if (!cancelled) setLesson(detail);
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "课件加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [lessonId]);

  async function startLesson() {
    setStarting(true);
    setError("");
    try {
      const detail = await apiRequest<LessonDetail>(`/api/v1/lessons/${lessonId}/start`, {
        method: "POST",
      });
      setLesson(detail);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "启动课程失败");
    } finally {
      setStarting(false);
    }
  }

  async function submitAttempt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lesson?.progress || !response.trim() || lesson.progress.current_step >= 3) return;
    const activity = stepMeta[lesson.progress.current_step].key;
    setAttempting(true);
    setError("");
    try {
      const result = await apiRequest<LessonAttemptResult>(
        `/api/v1/lessons/${lesson.id}/attempts`,
        {
          method: "POST",
          body: JSON.stringify({ activity, response: response.trim() }),
        },
      );
      setAttemptResult(result);
      setLesson((current) => current ? { ...current, progress: result.progress } : current);
      if (result.passed) {
        setResponse("");
        setShowKnowledge(false);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "练习提交失败");
    } finally {
      setAttempting(false);
    }
  }

  async function askTutor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lesson?.progress || !question.trim()) return;
    setAsking(true);
    setError("");
    try {
      const answer = await apiRequest<{
        user_message: LessonMessage;
        assistant_message: LessonMessage;
      }>(`/api/v1/lessons/${lesson.id}/ask`, {
        method: "POST",
        body: JSON.stringify({ question: question.trim() }),
      });
      setLesson((current) => current
        ? {
            ...current,
            messages: [...current.messages, answer.user_message, answer.assistant_message],
          }
        : current);
      setQuestion("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "问题发送失败");
    } finally {
      setAsking(false);
    }
  }

  if (loading) {
    return <main className="conversationLoading" id="main-content" tabIndex={-1}><div className="loadingPulse" /><p>正在注入本课上下文…</p></main>;
  }
  if (!lesson) {
    return <main className="conversationLoading" id="main-content" tabIndex={-1}><p>{error || "没有找到这节课"}</p><Link href="/courses">返回课程目录</Link></main>;
  }

  const currentStep = lesson.progress?.current_step ?? 0;
  const progressPercent = [0, 34, 67, 100][currentStep];
  const activity: LessonActivity | null = currentStep < 3
    ? [
        lesson.content.guided_practice,
        lesson.content.retrieval_practice,
        lesson.content.transfer_task,
      ][currentStep]
    : null;
  const showLessonKnowledge = currentStep === 0 || showKnowledge || currentStep === 3;

  return (
    <AppShell
      active="courses"
      panel={(
        <div className="lessonTutorPanel">
          <header>
            <span>文</span>
            <div><strong>小文老师</strong><small>仅使用第 {lesson.position} 课上下文</small></div>
          </header>
          <div className="lessonContextNotice">
            <span className="sectionLabel">CONTEXT PACK</span>
            <strong>{lesson.objective}</strong>
            <p>只注入 Mission 片段、本课知识、相关已确认错误和本课最近 6 条消息。</p>
          </div>
          <div className="lessonChatStream" aria-live="polite">
            {!lesson.messages.length ? (
              <article className="assistant">
                <span>文</span>
                <div><p>这节课只解决一个目标。哪里不清楚，可以随时问我。</p><small>本课上下文已就绪</small></div>
              </article>
            ) : null}
            {lesson.messages.map((message) => (
              <article className={message.role} key={message.id}>
                <span>{message.role === "assistant" ? "文" : "你"}</span>
                <div>
                  <p>{message.content}</p>
                  <small>{message.role === "assistant" ? `${message.provider} / ${message.model}` : "学习者提问"}</small>
                </div>
              </article>
            ))}
          </div>
          {lesson.progress ? (
            <form className="lessonTutorComposer" onSubmit={askTutor}>
              <label className="srOnly" htmlFor="lesson-question">向本课 AI 老师提问</label>
              <textarea
                id="lesson-question"
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="只问与本课有关的问题…"
                rows={3}
                value={question}
              />
              <button disabled={asking || !question.trim()} type="submit">{asking ? "…" : "发送"}</button>
            </form>
          ) : <p className="tutorLocked">开始本课后即可提问。</p>}
        </div>
      )}
      panelLabel="课内老师"
      sidebar={(
        <>
          <Link className="backLink" href="/courses">← 返回课程目录</Link>
          <div className="lessonSidebarTitle">
            <span className="sectionLabel lightLabel">COURSE {lesson.course_version}.0</span>
            <h1>{lesson.course_title}</h1>
            <p>第 {lesson.position} 课 · {lesson.estimated_minutes} 分钟</p>
          </div>
          <ol className="lessonStepList">
            {stepMeta.map((step, index) => (
              <li
                className={currentStep > index ? "done" : currentStep === index ? "active" : ""}
                key={step.key}
              >
                <span>{currentStep > index ? "✓" : index + 1}</span>
                <div><strong>{step.label}</strong><small>{step.note}</small></div>
              </li>
            ))}
          </ol>
          <div className="lessonSidebarPolicy">
            <strong>完成标准</strong>
            <p>浏览不算掌握；必须完成一次无提示迁移产出。</p>
          </div>
        </>
      )}
    >
      <div className="stackColumn">
      <header className="lessonHeader">
        <div>
          <span>{lesson.framework} · {lesson.level}</span>
          <strong>{lesson.title}</strong>
        </div>
        <div className="lessonProgressBar" aria-label={`课程进度 ${progressPercent}%`}>
          <span style={{ width: `${progressPercent}%` }} />
        </div>
        <span>{progressPercent}%</span>
      </header>

      <div className="lessonCanvas">
        <section className="lessonObjective reveal">
            <span className="sectionLabel">ONE OBSERVABLE OBJECTIVE</span>
            <h2>{lesson.objective}</h2>
            <div>{lesson.targets.map((target) => <span key={target}>{target}</span>)}</div>
          </section>

          {!lesson.progress ? (
            <section className="lessonStartGate reveal">
              <strong>准备好开始了吗？</strong>
              <p>开始后会创建独立课程工作区，并保存每次产出证据与提问记录。</p>
              <button className="primaryButton" disabled={starting} onClick={() => void startLesson()}>
                {starting ? "正在创建工作区…" : "开始本课"}
              </button>
            </section>
          ) : (
            <>
              {showLessonKnowledge ? (
                <section className="lessonKnowledge reveal">
                  <div className="lessonKnowledgeHeading">
                    <div><span className="sectionLabel">JUST ENOUGH KNOWLEDGE</span><h3>只学完成任务所需的内容</h3></div>
                    {currentStep > 0 && currentStep < 3 ? <button onClick={() => setShowKnowledge(false)}>收起提示</button> : null}
                  </div>
                  <p>{lesson.content.explanation}</p>
                  <div className="lessonExamples">
                    {lesson.content.examples.map((example) => (
                      <article key={example.chinese}>
                        <strong>{example.chinese}</strong>
                        {example.pinyin ? <span>{example.pinyin}</span> : null}
                        <p>{example.note}</p>
                      </article>
                    ))}
                  </div>
                </section>
              ) : currentStep < 3 ? (
                <button className="revealKnowledge" onClick={() => setShowKnowledge(true)}>
                  需要提示？查看本课知识（会降低检索难度）
                </button>
              ) : null}

              {currentStep < 3 && activity ? (
                <section className={`lessonPractice step-${currentStep} reveal`}>
                  <div className="practiceStage">
                    <span>STEP {currentStep + 1} / 3</span>
                    <strong>{stepMeta[currentStep].label}</strong>
                  </div>
                  <h3>{activity.prompt}</h3>
                  <form onSubmit={submitAttempt}>
                    <label htmlFor="lesson-response">用中文完成任务</label>
                    <textarea
                      id="lesson-response"
                      onChange={(event) => setResponse(event.target.value)}
                      placeholder="先自己说出来，再写在这里…"
                      rows={4}
                      value={response}
                    />
                    <button className="primaryButton" disabled={attempting || !response.trim()} type="submit">
                      {attempting ? "正在核对证据…" : "提交这次产出"}
                    </button>
                  </form>
                  {attemptResult && attemptResult.progress.current_step === currentStep ? (
                    <div className={attemptResult.passed ? "attemptFeedback passed" : "attemptFeedback"} role="status">
                      <strong>{attemptResult.passed ? "通过" : "还差一点"}</strong>
                      <p>{attemptResult.feedback}</p>
                      {attemptResult.missing_targets.length ? <small>需要补充：{attemptResult.missing_targets.join("、")}</small> : null}
                    </div>
                  ) : null}
                </section>
              ) : (
                <section className="lessonComplete reveal">
                  <span>✓</span>
                  <div>
                    <span className="sectionLabel">DEMONSTRATED EVIDENCE</span>
                    <h3>你不是“看完了”，而是已经用出来了</h3>
                    <p>{lesson.content.completion_evidence}</p>
                    <strong>{lesson.content.next_review}</strong>
                  </div>
                  <Link className="secondaryButton buttonLink" href="/courses">返回课程目录</Link>
                </section>
              )}

              <section className="lessonSources reveal">
                <span className="sectionLabel">SOURCE NOTES</span>
                <p>课件为原创练习，能力框架与考试范围依据以下官方来源；不复制教材或试卷正文。</p>
                {lesson.sources.map((source) => (
                  <a href={source.url} key={source.id} rel="noreferrer" target="_blank">
                    <strong>{source.title}</strong><span>{source.publisher} ↗</span>
                  </a>
                ))}
              </section>
            </>
          )}
          {error ? <p className="reportError" role="alert">{error}</p> : null}
      </div>
      </div>
    </AppShell>
  );
}
