"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, type MouseEvent, useState } from "react";

import { apiRequest, type OnboardingState } from "@/lib/api";

const hskOptions = ["not_sure", "HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6"];
const priorityOptions = [
  { value: "daily_life", label: "日常生活", note: "点餐、购物、出行" },
  { value: "campus", label: "校园交流", note: "课堂、宿舍、办事" },
  { value: "hsk_exam", label: "HSK 考试", note: "词汇、题型、应试" },
  { value: "internship", label: "实习求职", note: "面试与职场表达" },
  { value: "social", label: "社交沟通", note: "认识朋友与文化语用" },
];
const assessmentLabels = { listening: "听力", speaking: "口语", reading: "阅读", writing: "写作" };
type AssessmentKey = keyof typeof assessmentLabels;

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    displayName: "Alex Morgan", nativeLanguage: "English", supportLanguage: "English", hskBand: "HSK2",
    why: "I want to study and live independently in China.", success: "I can handle campus conversations and pass HSK 3.",
    deadline: "", weeklyMinutes: 180, priorities: ["campus", "hsk_exam"],
    assessment: { listening: 3, speaking: 2, reading: 3, writing: 2 },
    correctionMode: "turn_end", speechSpeed: "slow", showPinyin: true, englishFirst: false,
    reviewIntervalDays: 3, learningMemory: true, audioRetention: false, privacyAcknowledged: false,
  });

  function togglePriority(value: string) {
    setForm((current) => {
      const selected = current.priorities.includes(value);
      if (!selected && current.priorities.length >= 3) return current;
      return { ...current, priorities: selected ? current.priorities.filter((item) => item !== value) : [...current.priorities, value] };
    });
  }

  function nextStep(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    if (step === 2 && (!form.why.trim() || !form.success.trim() || form.priorities.length === 0)) {
      setError("请填写学习目标，并至少选择一个重点场景。"); return;
    }
    setError(""); setStep((current) => Math.min(4, current + 1));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.privacyAcknowledged) { setError("需要先确认隐私说明，才能保存学习档案。"); return; }
    setSaving(true); setError("");
    try {
      await apiRequest<OnboardingState>("/api/v1/onboarding", {
        method: "PUT",
        body: JSON.stringify({
          display_name: form.displayName, locale: "zh-CN",
          consent: { policy_version: "2026-08", privacy_acknowledged: form.privacyAcknowledged, learning_memory: form.learningMemory, audio_retention: form.audioRetention },
          mission: { why: form.why, success_looks_like: [form.success], constraints: [`每周可学习 ${form.weeklyMinutes} 分钟`], out_of_scope: [], priorities: form.priorities, weekly_minutes: form.weeklyMinutes, deadline: form.deadline || null },
          profile: { native_language: form.nativeLanguage, support_language: form.supportLanguage, current_hsk_band: form.hskBand, self_assessment: form.assessment, correction_mode: form.correctionMode, speech_speed: form.speechSpeed, show_pinyin: form.showPinyin, english_first: form.englishFirst, review_interval_days: form.reviewIntervalDays },
        }),
      });
      router.push("/");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "保存失败，请重试。");
    } finally { setSaving(false); }
  }

  return (
    <main className="onboardingShell" id="main-content" tabIndex={-1}>
      <aside className="onboardingIntro">
        <Link className="onboardingBrand" href="/"><span>汉</span> HanziMate</Link>
        <div><span className="sectionLabel lightLabel">LEARNING MISSION</span><h1>先认识你的目标，<br />再开始教中文。</h1><p>这里不会做一次性“贴标签”。你的水平判断会随着真实练习证据持续更新。</p></div>
        <div className="privacyPromise"><strong>你始终拥有控制权</strong><span>可查看、更正和删除 AI 记住的学习内容；原始录音默认不保存。</span></div>
      </aside>

      <section className="onboardingFormPane">
        <header className="onboardingTopbar"><Link href="/">← 返回工作区</Link><span>步骤 {step} / 4</span></header>
        <div className="stepTrack" aria-label={`建档进度 ${step}/4`}><span style={{ width: `${step * 25}%` }} /></div>
        <form className="onboardingForm" onSubmit={submit}>
          {step === 1 ? <fieldset>
            <legend>从你的语言背景开始</legend><p className="formLead">辅助语言只用于解释难点，学习过程会逐步增加中文比例。</p>
            <label>怎么称呼你？<input value={form.displayName} onChange={(event) => setForm({ ...form, displayName: event.target.value })} required /></label>
            <div className="formGrid"><label>母语<input value={form.nativeLanguage} onChange={(event) => setForm({ ...form, nativeLanguage: event.target.value })} required /></label><label>辅助语言<input value={form.supportLanguage} onChange={(event) => setForm({ ...form, supportLanguage: event.target.value })} required /></label></div>
            <label>目前大约的 HSK 水平<select value={form.hskBand} onChange={(event) => setForm({ ...form, hskBand: event.target.value })}>{hskOptions.map((option) => <option key={option} value={option}>{option === "not_sure" ? "不确定" : option}</option>)}</select></label>
          </fieldset> : null}

          {step === 2 ? <fieldset>
            <legend>定义你的 Learning Mission</legend><p className="formLead">目标越具体，AI 越容易选择刚好够得着的下一步。</p>
            <label>为什么现在想学中文？<textarea rows={3} value={form.why} onChange={(event) => setForm({ ...form, why: event.target.value })} required /></label>
            <label>什么结果代表“学成了”？<textarea rows={2} value={form.success} onChange={(event) => setForm({ ...form, success: event.target.value })} required /></label>
            <div className="choiceGrid">{priorityOptions.map((option) => <button className={form.priorities.includes(option.value) ? "choiceCard selected" : "choiceCard"} key={option.value} onClick={() => togglePriority(option.value)} type="button"><strong>{option.label}</strong><span>{option.note}</span></button>)}</div>
            <div className="formGrid"><label>每周可学习分钟<input min="30" max="1200" type="number" value={form.weeklyMinutes} onChange={(event) => setForm({ ...form, weeklyMinutes: Number(event.target.value) })} /></label><label>目标日期（可选）<input type="date" value={form.deadline} onChange={(event) => setForm({ ...form, deadline: event.target.value })} /></label></div>
          </fieldset> : null}

          {step === 3 ? <fieldset>
            <legend>给出一个起点，而不是最终结论</legend><p className="formLead">1 表示“刚开始”，5 表示“能较独立完成”。后续会用练习证据修正。</p>
            <div className="assessmentList">{(Object.keys(assessmentLabels) as AssessmentKey[]).map((key) => <label key={key}><span>{assessmentLabels[key]}</span><input min="1" max="5" type="range" value={form.assessment[key]} onChange={(event) => setForm({ ...form, assessment: { ...form.assessment, [key]: Number(event.target.value) } })} /><strong>{form.assessment[key]}</strong></label>)}</div>
            <div className="formGrid"><label>纠错时机<select value={form.correctionMode} onChange={(event) => setForm({ ...form, correctionMode: event.target.value })}><option value="instant">即时纠正</option><option value="turn_end">每轮结束</option><option value="session_end">整场结束</option></select></label><label>AI 语速<select value={form.speechSpeed} onChange={(event) => setForm({ ...form, speechSpeed: event.target.value })}><option value="slow">慢速</option><option value="normal">正常</option></select></label></div>
            <div className="switchList"><label><input checked={form.showPinyin} onChange={(event) => setForm({ ...form, showPinyin: event.target.checked })} type="checkbox" /> 生词默认显示拼音</label><label><input checked={form.englishFirst} onChange={(event) => setForm({ ...form, englishFirst: event.target.checked })} type="checkbox" /> 难点先用英文解释</label></div>
          </fieldset> : null}

          {step === 4 ? <fieldset>
            <legend>决定 AI 可以记住什么</legend><p className="formLead">长期画像保存“带来源的学习证据”，不会把整段聊天直接当作事实。</p>
            <div className="consentCards"><label><input checked={form.learningMemory} onChange={(event) => setForm({ ...form, learningMemory: event.target.checked })} type="checkbox" /><span><strong>个性化学习记忆</strong><small>记录已确认的错误、偏好与掌握证据；随时可删除。</small></span></label><label><input checked={false} disabled type="checkbox" /><span><strong>原始录音（MVP 暂不保存）</strong><small>当前只实时处理音频并保存必要转写；录音存储开放前会重新征得同意。</small></span></label><label className="requiredConsent"><input checked={form.privacyAcknowledged} onChange={(event) => setForm({ ...form, privacyAcknowledged: event.target.checked })} type="checkbox" /><span><strong>我已了解数据使用方式</strong><small>同意保存建档、学习进度及上述由我选择的内容。</small></span></label></div>
          </fieldset> : null}

          {error ? <p className="formError" role="alert">{error}</p> : null}
          <div className="formActions">{step > 1 ? <button className="secondaryButton" onClick={() => { setError(""); setStep(step - 1); }} type="button">上一步</button> : <span />}{step < 4 ? <button className="primaryButton" onClick={nextStep} type="button">继续</button> : <button className="primaryButton" disabled={saving} type="submit">{saving ? "正在生成…" : "生成我的学习空间"}</button>}</div>
        </form>
      </section>
    </main>
  );
}
