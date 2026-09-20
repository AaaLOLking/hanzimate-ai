"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  apiRequest,
  type ConversationScenario,
  type VoiceSessionCreated,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import {
  buildPracticeSessionPayload,
  type CorrectionMode,
  type PracticeMode,
} from "@/lib/practice";

export default function PracticePage() {
  const router = useRouter();
  const { t } = useI18n();
  const [scenarios, setScenarios] = useState<ConversationScenario[]>([]);
  const [practiceMode, setPracticeMode] = useState<PracticeMode>("scenario");
  const [selectedScenarioId, setSelectedScenarioId] = useState("");
  const [customObjective, setCustomObjective] = useState("");
  const [correctionMode, setCorrectionMode] = useState<CorrectionMode>("coach");
  const [connectionState, setConnectionState] = useState<"loading" | "ready" | "offline">("loading");
  const [starting, setStarting] = useState<null | "voice" | "text">(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    apiRequest<ConversationScenario[]>("/api/v1/voice/scenarios")
      .then((catalog) => {
        if (cancelled) return;
        setScenarios(catalog);
        setSelectedScenarioId((current) => current || catalog[0]?.id || "");
        setConnectionState("ready");
      })
      .catch(() => {
        if (!cancelled) setConnectionState("offline");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedScenario = scenarios.find((scenario) => scenario.id === selectedScenarioId);
  const startDisabled =
    starting !== null ||
    connectionState !== "ready" ||
    (practiceMode === "scenario" && !selectedScenario) ||
    (practiceMode === "custom" && !customObjective.trim());

  async function startPractice(useMicrophone: boolean) {
    if (practiceMode === "custom" && !customObjective.trim()) {
      setError(t("practice.customRequired"));
      return;
    }
    if (practiceMode === "scenario" && !selectedScenario) {
      setError(t("practice.scenarioRequired"));
      return;
    }
    setError("");
    setStarting(useMicrophone ? "voice" : "text");
    try {
      // No workspace_id: the backend creates a fresh conversation workspace per
      // practice, so repeated practices never clobber an older workspace state.
      const created = await apiRequest<VoiceSessionCreated>("/api/v1/voice/sessions", {
        method: "POST",
        body: JSON.stringify(buildPracticeSessionPayload({
          practiceMode,
          customObjective,
          scenarioId: selectedScenario?.id,
          scenarioTitle: selectedScenario?.title,
          correctionMode,
          speechSpeed: "slow",
          patience: "patient",
        })),
      });
      router.push(`/conversation/${created.session.workspace_id}?join=${useMicrophone ? "voice" : "text"}`);
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : t("practice.createFailed"));
      setStarting(null);
    }
  }

  const modeCards: Array<{ mode: PracticeMode; titleKey: Parameters<typeof t>[0]; copyKey: Parameters<typeof t>[0] }> = [
    { mode: "scenario", titleKey: "practice.modeScenario", copyKey: "practice.modeScenarioCopy" },
    { mode: "free", titleKey: "practice.modeFree", copyKey: "practice.modeFreeCopy" },
    { mode: "custom", titleKey: "practice.modeCustom", copyKey: "practice.modeCustomCopy" },
  ];

  const correctionOptions: Array<{ mode: CorrectionMode; labelKey: Parameters<typeof t>[0] }> = [
    { mode: "immersion", labelKey: "practice.correctionImmersion" },
    { mode: "coach", labelKey: "practice.correctionCoach" },
    { mode: "exam", labelKey: "practice.correctionExam" },
  ];

  return (
    <AppShell
      active="conversation"
      panel={(
        <div className="liveCoachPanel">
          <div className="coachIdentity"><span>文</span><div><strong>{t("practice.coachName")}</strong><small>{t("practice.coachRole")}</small></div></div>
          <section>
            <span className="sectionLabel">{t("practice.objectiveLabel")}</span>
            <p>{practiceMode === "scenario"
              ? selectedScenario?.objective ?? t("practice.objectiveScenarioFallback")
              : practiceMode === "free"
                ? t("practice.objectiveFree")
                : customObjective.trim() || t("practice.objectiveCustomFallback")}</p>
          </section>
          <section>
            <span className="sectionLabel">{t("practice.correctionLabel")}</span>
            <div className="practiceCorrectionPick" role="group" aria-label={t("practice.correctionLabel")}>
              {correctionOptions.map((option) => (
                <button
                  aria-pressed={correctionMode === option.mode}
                  className={correctionMode === option.mode ? "active" : ""}
                  key={option.mode}
                  onClick={() => setCorrectionMode(option.mode)}
                  type="button"
                >
                  {t(option.labelKey)}
                </button>
              ))}
            </div>
          </section>
          {selectedScenario?.prompt_starters.length && practiceMode === "scenario" ? (
            <section className="liveTips">
              <span className="sectionLabel">{t("practice.startersLabel")}</span>
              {selectedScenario.prompt_starters.map((starter) => <p key={starter}>{starter}</p>)}
            </section>
          ) : null}
          {selectedScenario?.safety_note && practiceMode === "scenario" ? (
            <div className="safetyNotice"><strong>{t("practice.safetyTitle")}</strong><p>{selectedScenario.safety_note}</p></div>
          ) : null}
          <div className="livePrivacy"><strong>{t("practice.privacyTitle")}</strong><span>{t("practice.privacyCopy")}</span></div>
        </div>
      )}
      panelLabel={t("practice.panelLabel")}
      sidebar={(
        <>
          <Link className="backLink" href="/">{t("practice.back")}</Link>
          <div className="scenarioBlock">
            <span className="sectionLabel lightLabel">{t("practice.sideLabel")}</span>
            <h1>{t("practice.sideTitle")}</h1>
            <p>{t("practice.sideCopy")}</p>
          </div>
        </>
      )}
    >
      <div className="stackColumn">
        <header className="workspaceHeader">
          <div>
            <div className="eyebrow">{t("practice.eyebrow")}</div>
            <h1>{t("practice.title")}</h1>
          </div>
          <div className="headerActions">
            <span className="modelPill"><i /> {t("practice.livePill")}</span>
          </div>
        </header>

        <div className="canvas">
          {connectionState === "offline" ? <div className="apiNotice errorNotice">{t("practice.apiOffline")}</div> : null}
          {connectionState === "loading" ? <p className="quietText">{t("practice.loading")}</p> : null}

          <section className="practiceModeGrid" aria-label={t("practice.eyebrow")}>
            {modeCards.map((card) => (
              <button
                aria-pressed={practiceMode === card.mode}
                className={practiceMode === card.mode ? "practiceModeCard active" : "practiceModeCard"}
                key={card.mode}
                onClick={() => setPracticeMode(card.mode)}
                type="button"
              >
                <strong>{t(card.titleKey)}</strong>
                <p>{t(card.copyKey)}</p>
              </button>
            ))}
          </section>

          {practiceMode === "scenario" ? (
            <section className="practiceDetail reveal">
              <div className="sectionHeading">
                <div>
                  <span className="sectionLabel">SCENARIO</span>
                  <h2>{t("practice.scenarioTitle")}</h2>
                </div>
              </div>
              <div className="scenarioPicker" aria-label={t("practice.scenarioTitle")}>
                {scenarios.map((scenario) => (
                  <button
                    aria-pressed={selectedScenarioId === scenario.id}
                    className={selectedScenarioId === scenario.id ? "active" : ""}
                    key={scenario.id}
                    onClick={() => setSelectedScenarioId(scenario.id)}
                    type="button"
                  >
                    <strong>{scenario.title}</strong>
                    <small>{scenario.level} · {scenario.category}</small>
                  </button>
                ))}
              </div>
            </section>
          ) : null}

          {practiceMode === "free" ? (
            <section className="practiceDetail reveal">
              <p className="practiceFreeCopy">{t("practice.freeCopy")}</p>
            </section>
          ) : null}

          {practiceMode === "custom" ? (
            <section className="practiceDetail reveal">
              <label className="customPracticeGoal">
                <span>{t("practice.customLabel")}</span>
                <textarea
                  maxLength={500}
                  onChange={(event) => setCustomObjective(event.target.value)}
                  placeholder={t("practice.customPlaceholder")}
                  rows={3}
                  value={customObjective}
                />
                <small>{t("practice.customCounter", { count: customObjective.length })}</small>
              </label>
            </section>
          ) : null}

          <div className="startActions practiceStartActions">
            <button className="primaryButton" disabled={startDisabled} onClick={() => void startPractice(true)}>
              <span className="micIcon">{starting === "voice" ? "…" : "●"}</span>
              {starting === "voice" ? t("practice.starting") : t("practice.startVoice")}
            </button>
            <button className="secondaryButton" disabled={startDisabled} onClick={() => void startPractice(false)}>
              {starting === "text" ? t("practice.starting") : t("practice.startText")}
            </button>
          </div>
          {error ? <div className="liveError" role="alert">{error}</div> : null}
        </div>
      </div>
    </AppShell>
  );
}
