"use client";

import { Bookmark, Clock3, Pause, Play, RotateCcw, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import AppShell from "../components/AppShell";
import { useAuth } from "../components/AuthProvider";
import PrimaryButton from "@/components/ui/primary-button";
import { ApiError } from "@/lib/auth-api";
import {
  completePracticeAttempt,
  getSubjects,
  savePracticeAnswer,
  startPracticeAttempt,
  type AttemptSummary,
  type PracticeAttempt,
  type Subject,
} from "@/lib/study-api";

const formatTime = (seconds: number) => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
const initialQueryValue = (key: string, fallback = "") => typeof window === "undefined" ? fallback : new URLSearchParams(window.location.search).get(key) || fallback;

export default function PracticePage() {
  const { accessToken } = useAuth();
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [subjectSlug, setSubjectSlug] = useState(() => initialQueryValue("subject", "english"));
  const [topicSlug, setTopicSlug] = useState(() => initialQueryValue("topic"));
  const [attempt, setAttempt] = useState<PracticeAttempt | null>(null);
  const [summary, setSummary] = useState<AttemptSummary | null>(null);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [marked, setMarked] = useState<Record<string, boolean>>({});
  const [remaining, setRemaining] = useState(1800);
  const [paused, setPaused] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getSubjects().then(setSubjects).catch((reason: unknown) => setError(reason instanceof ApiError ? reason.message : "Practice filters could not be loaded."));
  }, []);

  useEffect(() => { if (error) toast.error("Practice needs attention", { description: error, id: "practice-error" }); }, [error]);

  useEffect(() => {
    if (!attempt || paused || summary || remaining <= 0) return;
    const timer = window.setInterval(() => setRemaining(value => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [attempt, paused, remaining, summary]);

  const selectedSubject = subjects.find(subject => subject.slug === subjectSlug);
  const availableTopics = selectedSubject?.topics ?? [];
  const question = attempt?.questions[current];
  const selected = question ? answers[question.id] : undefined;
  const elapsed = attempt ? attempt.duration_seconds - remaining : 0;

  const start = async () => {
    if (!accessToken) return;
    setBusy(true); setError(""); setSummary(null);
    try {
      const nextAttempt = await startPracticeAttempt(accessToken, { subject_slug: subjectSlug, topic_slug: topicSlug || undefined, question_count: 10 });
      setAttempt(nextAttempt); setRemaining(nextAttempt.duration_seconds); setCurrent(0); setAnswers({}); setMarked({}); setPaused(false);
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Practice could not be started."); }
    finally { setBusy(false); }
  };

  const saveAndMove = async () => {
    if (!accessToken || !attempt || !question || selected === undefined) return;
    setBusy(true); setError("");
    try {
      await savePracticeAnswer(accessToken, attempt.id, question.id, { selected_index: selected, marked_for_review: Boolean(marked[question.id]) });
      if (current < attempt.questions.length - 1) setCurrent(index => index + 1);
      else setSummary(await completePracticeAttempt(accessToken, attempt.id, Math.max(0, elapsed)));
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Your answer could not be saved."); }
    finally { setBusy(false); }
  };

  const finish = async () => {
    if (!accessToken || !attempt) return;
    setBusy(true); setError("");
    try { setSummary(await completePracticeAttempt(accessToken, attempt.id, Math.max(0, elapsed))); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "The set could not be submitted."); }
    finally { setBusy(false); }
  };

  const answeredCount = useMemo(() => Object.keys(answers).length, [answers]);

  return <AppShell active="Practice"><main className="workspace practice-workspace">
    <header className="workspace-header"><div><span className="workspace-kicker">Build the daily habit</span><h1>Daily practice</h1><p>A focused question set with exam-like controls and a calm review flow.</p></div><div className="workspace-badge"><ShieldCheck size={15} /> Saved to your account</div></header>
    <section className="practice-controls">
      <select aria-label="Subject" value={subjectSlug} disabled={Boolean(attempt && !summary)} onChange={event => { setSubjectSlug(event.target.value); setTopicSlug(""); }}>{subjects.map(subject => <option value={subject.slug} key={subject.id}>{subject.name}</option>)}</select>
      <select aria-label="Topic" value={topicSlug} disabled={Boolean(attempt && !summary)} onChange={event => setTopicSlug(event.target.value)}><option value="">All topics</option>{availableTopics.map(topic => <option value={topic.slug} key={topic.id}>{topic.name}</option>)}</select>
      <span />
      <div className="practice-timer"><Clock3 size={16} /><small>Time remaining</small><strong>{formatTime(remaining)}</strong><button disabled={!attempt || Boolean(summary)} onClick={() => setPaused(!paused)}>{paused ? <Play size={15} /> : <Pause size={15} />}</button></div>
    </section>
    {summary ? <section className="practice-start practice-summary"><span><ShieldCheck size={26} /></span><h2>Practice set complete</h2><p>Your result is calculated from the answers saved in your account.</p><div><small>Score</small><strong>{summary.correct_answers} / {summary.total_questions}</strong><small>Accuracy</small><strong>{summary.accuracy}%</strong><small>Time</small><strong>{formatTime(summary.duration_seconds)}</strong></div><PrimaryButton href="/progress">View your progress</PrimaryButton><button className="practice-again" onClick={() => { setAttempt(null); setSummary(null); }}>Practise another set</button></section>
      : !attempt ? <section className="practice-start"><span><Play size={26} /></span><h2>Today’s practice is ready</h2><p>Questions are selected from the subject and topic you choose. Every completed set updates your real progress.</p><div><small>Subject</small><strong>{selectedSubject?.name ?? "Loading…"}</strong><small>Set length</small><strong>Up to 10 questions</strong><small>Timer</small><strong>30 minutes</strong></div><PrimaryButton onClick={() => void start()} disabled={busy || subjects.length === 0}>{busy ? "Preparing…" : "Start practice"} <Play size={16} /></PrimaryButton></section>
      : question && <section className="question-shell"><header><span>Question {String(current + 1).padStart(2, "0")} <small>/ {attempt.questions.length}</small></span><button className={marked[question.id] ? "marked" : ""} onClick={() => setMarked(values => ({ ...values, [question.id]: !values[question.id] }))}><Bookmark size={15} /> {marked[question.id] ? "Marked" : "Mark for review"}</button></header><div className="question-body"><span className="question-topic">{question.subject} · {question.topic}</span><h2>{question.prompt}</h2>{question.context && <p>{question.context}</p>}<div className="mcq-options">{question.options.map((option, index) => <button className={selected === index ? "selected" : ""} onClick={() => setAnswers(values => ({ ...values, [question.id]: index }))} key={option}><span>{String.fromCharCode(65 + index)}</span>{option}</button>)}</div></div><footer><button onClick={() => { setAttempt(null); setAnswers({}); setRemaining(1800); }}><RotateCcw size={15} /> Leave set</button><div>{current > 0 && <button className="secondary-question-button" onClick={() => setCurrent(index => index - 1)}>Previous</button>}{answeredCount > 0 && current < attempt.questions.length - 1 && <button className="secondary-question-button" onClick={() => void finish()}>Submit set</button>}<PrimaryButton onClick={() => void saveAndMove()} className="next-question-button" size="sm" disabled={selected === undefined || busy}>{current === attempt.questions.length - 1 ? "Submit set" : "Save & next"}</PrimaryButton></div></footer></section>}
  </main></AppShell>;
}
