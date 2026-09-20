"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { Panel } from "@/components/panel";
import { apiRequest, type ErrorCluster, type ModelOption, type OnboardingState, type Workspace } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { type ReviewDashboard, reviewDate } from "@/lib/reviews";

export default function Home() {
  const router = useRouter();
  const { t } = useI18n();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [onboarding, setOnboarding] = useState<OnboardingState | null>(null);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [reviews, setReviews] = useState<ReviewDashboard | null>(null);
  const [clusters, setClusters] = useState<ErrorCluster[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null);
  const [connectionState, setConnectionState] = useState<"loading" | "ready" | "offline">("loading");

  useEffect(() => {
    Promise.all([
      apiRequest<OnboardingState>("/api/v1/onboarding"),
      apiRequest<Workspace[]>("/api/v1/workspaces"),
      apiRequest<ModelOption[]>("/api/v1/models"),
      apiRequest<ReviewDashboard>("/api/v1/reviews"),
      apiRequest<ErrorCluster[]>("/api/v1/error-clusters"),
    ])
      .then(([nextOnboarding, nextWorkspaces, nextModels, nextReviews, nextClusters]) => {
        setOnboarding(nextOnboarding);
        setWorkspaces(nextWorkspaces);
        setModels(nextModels);
        setReviews(nextReviews);
        setClusters(nextClusters);
        setSelectedWorkspace(nextWorkspaces[0] ?? null);
        setConnectionState("ready");
      })
      .catch(() => setConnectionState("offline"));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setInterval(() => {
      void apiRequest<ReviewDashboard>("/api/v1/reviews")
        .then((next) => { if (!cancelled) setReviews(next); })
        .catch(() => { /* Keep the last visible data; manual navigation can retry. */ });
    }, 60000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, []);

  async function restoreWorkspace(workspaceId: string) {
    try {
      const restored = await apiRequest<Workspace>(`/api/v1/workspaces/${workspaceId}`);
      setSelectedWorkspace(restored);
      setWorkspaces((current) => [restored, ...current.filter((item) => item.id !== restored.id)]);
      const lessonVersionId = restored.state.lesson_version_id;
      if (restored.kind === "lesson" && typeof lessonVersionId === "string") {
        router.push(`/lessons/${lessonVersionId}`);
      }
    } catch {
      setConnectionState("offline");
    }
  }

  const missionHeadline = selectedWorkspace?.title ?? onboarding?.mission?.success_looks_like[0] ?? t("home.missionFallback");
  const missionDescription = (selectedWorkspace?.state.objective as string | undefined) ?? onboarding?.mission?.why ?? t("home.missionDescFallback");
  const modelName = models[0]?.display_name ?? t("home.modelFallback");
  const conversationWorkspace = selectedWorkspace?.kind === "conversation"
    ? selectedWorkspace
    : workspaces.find((workspace) => workspace.kind === "conversation") ?? null;
  const workspaceKindLabel = (kind: Workspace["kind"]) =>
    kind === "conversation" ? t("home.kindConversation") : kind === "lesson" ? t("home.kindLesson") : t("home.kindReview");
  const workspaceStatusLabel = (status: Workspace["status"]) =>
    status === "active"
      ? t("home.statusActive")
      : status === "review_due"
        ? t("home.statusReviewDue")
        : status === "completed"
          ? t("home.statusCompleted")
          : t("home.statusProcessing");

  return (
    <AppShell
      active="home"
      panel={(
        <>
          <header className="coachHeader">
            <div>
              <span className="coachAvatar">文</span>
              <span>
                <strong>{t("home.coachName")}</strong>
                <small>{t("home.coachRole")}</small>
              </span>
            </div>
          </header>

          <div className="goalSummary">
            <span className="sectionLabel">{t("home.nextLabel")}</span>
            <p>{reviews?.due_count ? t("home.dueCopy", { count: reviews.due_count }) : t("home.noDueCopy")}</p>
          </div>

          <div className="chatStream">
            <div className="assistantMessage">
              <span className="miniAvatar">文</span>
              <div>
                <p>{t("home.tip1")}</p>
                <p>{t("home.tip2")}</p>
              </div>
            </div>
            <div className="suggestionChips">
              <Link className="secondaryButton buttonLink" href="/reviews">{t("home.gotoReviews")}</Link>
              <Link className="secondaryButton buttonLink" href="/courses">{t("home.gotoCourses")}</Link>
            </div>
          </div>

          <div className="contextNotice">
            <span>{t("home.privacyTitle")}</span>
            <Link href="/errors">{t("home.privacyCta")}</Link>
          </div>
        </>
      )}
      panelLabel={t("home.panelLabel")}
      sidebar={(
        <>
          <div className="workspaceHeading">
            <span>{t("home.workspacesTitle")}</span>
            <button aria-label={t("home.newWorkspace")} disabled title={t("home.soon")}>＋</button>
          </div>

          <div className="workspaceList">
            {workspaces.map((workspace) => (
              <button
                className={selectedWorkspace?.id === workspace.id ? "workspaceItem selected" : "workspaceItem"}
                key={workspace.id}
                onClick={() => restoreWorkspace(workspace.id)}
              >
                <span className="workspaceTitle">{workspace.title}</span>
                <span className="workspaceMeta">{workspaceKindLabel(workspace.kind)}</span>
                <span className={"status status-" + workspace.status}>
                  {workspaceStatusLabel(workspace.status)}
                </span>
              </button>
            ))}
            {connectionState === "ready" && workspaces.length === 0 ? <p className="emptyWorkspace">{t("home.emptyWorkspaces")}</p> : null}
          </div>
        </>
      )}
    >
      <header className="workspaceHeader">
        <div>
          <div className="eyebrow">{t("home.eyebrow")}</div>
          <h1>{t("home.headline")}</h1>
        </div>
        <div className="headerActions">
          <span className="modelPill"><i /> {modelName}</span>
          <Link className="secondaryButton buttonLink" href="/onboarding">{t("home.settings")}</Link>
        </div>
      </header>

      <div className="canvas">
        {connectionState === "offline" ? <div className="apiNotice errorNotice">{t("home.apiOffline")}</div> : null}
        {connectionState === "ready" && onboarding && !onboarding.complete ? (
          <div className="apiNotice setupNotice"><span><strong>{t("home.setupStrong")}</strong>{t("home.setupLead")}</span><Link href="/onboarding">{t("home.setupCta")}</Link></div>
        ) : null}
        <section className="missionCard">
          <div>
            <span className="sectionLabel">YOUR MISSION</span>
            <h2>{missionHeadline}</h2>
            <p>{missionDescription}</p>
          </div>
          <div className="missionProgress">
            <strong>{reviews?.reviewed_today ?? "—"}</strong>
            <span>{t("home.reviewedToday")}</span>
          </div>
        </section>

        <section className="sectionBlock reveal">
          <div className="sectionHeading">
            <div>
              <span className="sectionLabel">REVIEW DUE</span>
              <h2>{t("home.reviewTitle")}</h2>
            </div>
            <Link className="textButton" href="/reviews">{(reviews?.due_count ?? 0) + t("home.reviewCtaSuffix")}</Link>
          </div>
          {reviews?.reminder ? <div className="apiNotice setupNotice"><span>{t("home.reminderLead") + reviews.due_count + t("home.reminderTail")}</span><Link href="/reviews">{t("home.reviewNow")}</Link></div> : null}
          <div className="reviewGrid">
            {reviews?.cards.slice(0, 3).map((item, index) => (
              <Link href="/reviews" className="reviewCard panelCard panelCard--interactive" key={item.id}>
                <div className="reviewTop">
                  <span className="count">0{index + 1}</span>
                  <span className="dueDot">{t("home.dueNow")}</span>
                </div>
                <h3>{item.title}</h3>
                <p>{t("home.cardCopy")}</p>
                <span className="quietText">{t("home.cardCta")}</span>
              </Link>
            ))}
          </div>
          {reviews && !reviews.due_count ? <p className="quietText">
            {reviews.upcoming[0] ? t("home.noDueNext") + reviewDate(reviews.upcoming[0].due_at, reviews.preferences.timezone) : t("home.noDue")}
          </p> : null}
        </section>

        <section className="conversationCard reveal">
          <div className="conversationVisual" aria-hidden="true">
            <span className="soundBar short" />
            <span className="soundBar medium" />
            <span className="soundBar tall" />
            <span className="soundBar medium" />
            <span className="soundBar short" />
          </div>
          <div className="conversationCopy">
            <span className="sectionLabel">LIVE CONVERSATION</span>
            <h2>{(conversationWorkspace?.title ?? t("home.liveTitleFallback")) + t("home.liveSuffix")}</h2>
            <p>{t("home.liveCopy")}</p>
            <div className="conversationMeta">
              <span>{t("home.metaDuration")}</span>
              <span>{t("home.metaSpeed")}</span>
              <span>{t("home.metaLang")}</span>
            </div>
          </div>
          <Link
            className="primaryButton"
            href={onboarding?.complete ? "/practice" : "/onboarding"}
          >
            <span className="micIcon">●</span>
            {onboarding?.complete ? t("home.start") : t("home.startLocked")}
          </Link>
        </section>

        <section className="memoryPreview reveal">
          <div className="sectionHeading">
            <div>
              <span className="sectionLabel">FROM YOUR LAST SESSION</span>
              <h2>{t("home.memoryTitle")}</h2>
            </div>
            <Link className="textButton" href="/errors">{t("home.memoryCta")}</Link>
          </div>
          {clusters.slice(0, 1).map((cluster) => (
            <Panel className="correctionCard" key={cluster.id}>
              <span className="evidenceTag">{t("home.evidence")}</span>
              <div className="sentenceCompare">
                <strong>{cluster.corrected_example}</strong>
              </div>
              <p>{cluster.explanation}</p>
              <span className="skillTag">{t("home.confirmedTimes", { count: cluster.occurrence_count })}</span>
            </Panel>
          ))}
          {!clusters.length ? <p className="quietText">{t("home.noMemory")}</p> : null}
        </section>
      </div>
    </AppShell>
  );
}
