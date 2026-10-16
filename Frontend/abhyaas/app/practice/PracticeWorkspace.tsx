"use client";

import { ArrowLeft, ArrowRight, Bookmark, BookOpen, Check, Clock3, GraduationCap, History, Pause, Play, Sparkles, Target } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { checkpointPracticeAttempt, completePracticeAttempt, getPracticeAttempt, getPracticeHistory, getPracticeResult, getPracticeAvailability, getSubjects, startPracticeAttempt, startSimilarAttempt, type AttemptSummary, type PracticeAttempt, type PracticeHistoryItem, type PracticeAvailability, type PracticeProvenance, type Subject } from "@/lib/study-api";
import { practiceChoices, practiceSetSize, type PracticeMode } from "@/lib/practice-plan";
import { useAuth } from "../components/AuthProvider";
import PreparationTarget from "../components/PreparationTarget";
import { getPreparationTarget, partitionPreparationSubjects } from "@/lib/academy-preference";
import s from "./practice.module.css";
import { startDailyQuiz, type StudyTask } from "@/lib/study-plan-api";
import PracticeQuestionSkeleton from "./PracticeQuestionSkeleton";
import { createLatestSaveQueue } from "@/lib/latest-save-queue";

const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
const message = (error: unknown) => error instanceof Error ? error.message : "Something went wrong. Please try again.";

export default function PracticeWorkspace({ initialSubject, initialTopic = "", initialView = "practice", dailyTask }: { initialSubject: string; initialTopic?: string; initialView?: "practice" | "history"; dailyTask?: StudyTask }) {
  const { accessToken, user } = useAuth();
  const router = useRouter();
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [catalogVersion, setCatalogVersion] = useState(0);
  const [subjectSlug, setSubjectSlug] = useState(initialSubject);
  const [topicSlug, setTopicSlug] = useState(initialTopic);
  const [count, setCount] = useState(dailyTask ? dailyTask.quiz_remaining || dailyTask.question_count : 50);
  const [mode, setMode] = useState<PracticeMode>(dailyTask ? "mixed" : "fresh");
  const [availability, setAvailability] = useState<{ key: string; data: PracticeAvailability }>();
  const [preview, setPreview] = useState(false);
  const [attempt, setAttempt] = useState<PracticeAttempt | null>(null);
  const [summary, setSummary] = useState<AttemptSummary | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [marked, setMarked] = useState<Record<string, boolean>>({});
  const [current, setCurrent] = useState(0);
  const [remaining, setRemaining] = useState(1800);
  const [paused, setPaused] = useState(false);
  const [busy, setBusy] = useState(false);
  const [openingSet, setOpeningSet] = useState<{ count: number; subject?: string; topic?: string; prepared?: number } | null>(dailyTask ? { count: 50, subject: dailyTask.subject_name, topic: dailyTask.topic_name } : null);
  const [openingDelayed, setOpeningDelayed] = useState(false);
  const [error, setError] = useState("");
  const [saveStatus, setSaveStatus] = useState("");
  const [tab, setTab] = useState<"practice" | "history">(initialView);
  const [history, setHistory] = useState<PracticeHistoryItem[]>([]);
  const [historyMore, setHistoryMore] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [historyVersion, setHistoryVersion] = useState(0);
  const mutation = useRef(false);
  const saveQueue = useRef(createLatestSaveQueue<Parameters<typeof checkpointPracticeAttempt>>(
    (input) => checkpointPracticeAttempt(...input),
  ));
  const timedOut = useRef(false);
  const questionBody = useRef<HTMLDivElement>(null);
  const latestSave = useRef<(() => Promise<void>) | null>(null);
  const generation = useRef<AbortController | null>(null);
  const dailyStarted = useRef(false);
  const subject = subjects.find((item) => item.slug === subjectSlug) ?? subjects[0];
  const target = getPreparationTarget(user?.target_academy);
  const subjectGroups = partitionPreparationSubjects(subjects, user?.target_academy);
  const isExtraPractice = subjectGroups.optional.some((item) => item.slug === subjectSlug);
  const topic = subject?.topics.find((item) => item.slug === topicSlug);
  const availabilityKey = `${subjectSlug}:${topicSlug}:${historyVersion}`;
  const pool = availability?.key === availabilityKey ? availability.data : undefined;
  const setSize = practiceSetSize(mode, count, pool);
  const active = !!attempt && !summary && !preview;
  const question = attempt?.questions[current];
  const answerInput = useCallback(() => Object.entries(answers).map(([question_id, selected_index]) => ({ question_id, selected_index, marked_for_review: !!marked[question_id] })), [answers, marked]);

  useEffect(() => {
    if (!openingSet) return;
    const timer = window.setTimeout(() => setOpeningDelayed(true), 25_000);
    return () => window.clearTimeout(timer);
  }, [openingSet]);

  useEffect(() => { if (dailyTask) return; let alive = true; getSubjects().then((data) => { if (alive) { setSubjects(data); setError(""); } }).catch((e) => { if (alive) setError(message(e)); }); return () => { alive = false; }; }, [catalogVersion, dailyTask]);
  useEffect(() => {
    if (!accessToken || dailyTask) return;
    let alive = true;
    getPracticeAvailability(accessToken, subjectSlug, topicSlug).then((data) => { if (alive) setAvailability({ key: availabilityKey, data }); }).catch((e) => { if (alive) setError(message(e)); });
    return () => { alive = false; };
  }, [accessToken, subjectSlug, topicSlug, availabilityKey, dailyTask]);
  useEffect(() => {
    if (!accessToken || tab !== "history") return;
    let alive = true;
    queueMicrotask(() => { if (alive) { setHistoryLoading(true); setHistoryError(""); } });
    getPracticeHistory(accessToken).then((data) => { if (alive) { setHistory(data.items); setHistoryMore(data.has_more); } })
      .catch((e) => { if (alive) setHistoryError(message(e)); }).finally(() => { if (alive) setHistoryLoading(false); });
    return () => { alive = false; };
  }, [accessToken, tab, historyVersion]);
  useEffect(() => {
    if (!active || paused) return;
    let last = Date.now();
    const timer = window.setInterval(() => { const now = Date.now(); const elapsed = Math.floor((now - last) / 1000); if (elapsed) { last += elapsed * 1000; setRemaining((r) => Math.max(0, r - elapsed)); } }, 1000);
    return () => window.clearInterval(timer);
  }, [active, paused]);
  const persist = useCallback(async (keepalive = false, position = current) => {
    if (!accessToken || !attempt || summary || preview) return;
    await saveQueue.current.enqueue([accessToken, attempt.id, attempt.duration_seconds - remaining, answerInput(), position, keepalive]);
  }, [accessToken, attempt, summary, preview, remaining, answerInput, current]);
  useEffect(() => { latestSave.current = active ? () => persist(true) : null; }, [active, persist]);
  useEffect(() => () => { const pending = generation.current; generation.current = null; pending?.abort(); void latestSave.current?.().catch(() => {}); }, []);
  useEffect(() => {
    if (!active) return;
    const save = () => { if (!mutation.current) void latestSave.current?.().catch(() => setSaveStatus("Connection lost — progress will retry")); };
    const timer = window.setInterval(save, 15_000);
    window.addEventListener("pagehide", save);
    window.addEventListener("online", save);
    return () => { window.clearInterval(timer); window.removeEventListener("pagehide", save); window.removeEventListener("online", save); };
  }, [active]);
  useEffect(() => {
    if (!active) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [active]);
  // Serialize autosaves and final submission so older writes cannot overwrite newer answers.
  useEffect(() => {
    if (!active || busy) return;
    let alive = true;
    const timer = window.setTimeout(() => {
      if (mutation.current) return;
      setSaveStatus("Saving…");
      const save = latestSave.current?.() ?? Promise.resolve();
      save.then(() => { if (alive) setSaveStatus("Answers saved"); }).catch(() => { if (alive) setSaveStatus("Not saved — use Save & next to retry"); });
    }, 600);
    return () => { alive = false; window.clearTimeout(timer); };
  }, [active, busy, answerInput, current, paused]);
  useEffect(() => { questionBody.current?.scrollTo({ top: 0 }); }, [current]);
  const finish = useCallback(async () => {
    if (!accessToken || !attempt || mutation.current) return;
    mutation.current = true; setBusy(true); setError("");
    try {
      await saveQueue.current.drain();
      setSummary(await completePracticeAttempt(accessToken, attempt.id, attempt.duration_seconds - remaining, answerInput()));
      setHistoryVersion((v) => v + 1);
    } catch (e) { setError(message(e)); }
    finally { mutation.current = false; setBusy(false); }
  }, [accessToken, attempt, remaining, answerInput]);
  useEffect(() => {
    if (!active || remaining > 0 || timedOut.current || busy) return;
    timedOut.current = true;
    queueMicrotask(() => void finish());
  }, [active, remaining, busy, finish]);

  const leave = async (nextSubject?: string, nextTopic?: string, nextTab: "practice" | "history" = "practice") => {
    if (mutation.current) return;
    mutation.current = true; setBusy(true); setError("");
    try {
      if (active) await persist();
      setAttempt(null); setSummary(null); setPreview(false); setAnswers({}); setMarked({}); setSaveStatus("");
      if (nextSubject !== undefined) { setSubjectSlug(nextSubject); setTopicSlug(nextTopic ?? ""); }
      setTab(nextTab); setHistoryVersion((v) => v + 1);
    } catch (e) { setError(message(e)); }
    finally { mutation.current = false; setBusy(false); }
  };
  const returnToPlan = async () => {
    if (mutation.current) return;
    mutation.current = true; setBusy(true); setError("");
    try { if (active) await persist(); router.push("/progress#today"); }
    catch(e) { setError(message(e)); }
    finally { mutation.current = false; setBusy(false); }
  };
  const start = useCallback(async (choice: PracticeMode = mode) => {
    if (!accessToken || (!dailyTask && !subject) || mutation.current) return;
    const size = dailyTask ? 50 : practiceSetSize(choice, count, pool);
    if (!size) return;
    const controller = new AbortController();
    generation.current = controller;
    mutation.current = true; setBusy(true); setError(""); setOpeningDelayed(false);
    setOpeningSet({ count: size, subject: dailyTask?.subject_name ?? subject?.name, topic: dailyTask?.topic_name ?? topic?.name });
    const timeout = window.setTimeout(() => controller.abort(), dailyTask ? 360_000 : 165_000);
    try {
      setMode(choice);
      if (choice === "similar") setCount(size);
      const data = dailyTask ? await startDailyQuiz(accessToken, dailyTask.id, controller.signal, (prepared) => {
        if (generation.current === controller && !controller.signal.aborted) setOpeningSet((state) => state ? { ...state, prepared } : state);
      }) : choice === "similar"
        ? await startSimilarAttempt(accessToken, { subject_slug: subject!.slug, topic_slug: topic?.slug, question_count: size }, controller.signal)
        : await startPracticeAttempt(accessToken, { subject_slug: subject!.slug, topic_slug: topic?.slug, question_count: size, allow_repeats: choice === "mixed" }, controller.signal);
      // A cancelled request must not replace another set or restart its timer.
      if (generation.current !== controller || controller.signal.aborted) return;
      if (!data.questions.length) throw new Error("No questions were returned. Please try again.");
      setAttempt(data); setSummary(null); setPreview(false);
      setAnswers(Object.fromEntries(data.answers.map(a => [a.question_id, a.selected_index])));
      setMarked(Object.fromEntries(data.answers.map(a => [a.question_id, a.marked_for_review])));
      setCurrent(Math.min(data.current_position ?? 0, data.questions.length - 1));
      setRemaining(Math.max(0,data.duration_seconds - data.elapsed_seconds)); setPaused(false); setSaveStatus(""); timedOut.current = false;
    } catch (e) {
      if (generation.current === controller) setError(controller.signal.aborted ? dailyTask ? "Your full quiz couldn't be opened in time. Please retry; saved quizzes will resume." : "Preparing this set took too long. Try a smaller set or use the question bank." : message(e));
    } finally {
      window.clearTimeout(timeout);
      if (generation.current === controller) { generation.current = null; mutation.current = false; setBusy(false); setOpeningSet(null); }
    }
  }, [accessToken, dailyTask, subject, topic, mode, count, pool]);
  useEffect(() => {
    if (!dailyTask || !accessToken || dailyStarted.current) return;
    let alive = true;
    // Defer until committed; React's development effect replay cannot create two quizzes.
    queueMicrotask(() => { if (alive && !dailyStarted.current) { dailyStarted.current = true; void start(); } });
    return () => { alive = false; };
  }, [dailyTask, accessToken, start]);
  const cancelOpening = () => {
    dailyStarted.current = true;
    const pending = generation.current;
    generation.current = null;
    pending?.abort();
    mutation.current = false; setBusy(false); setOpeningSet(null); setOpeningDelayed(false);
  };
  const openHistory = async (item: PracticeHistoryItem) => {
    if (!accessToken || mutation.current) return;
    mutation.current = true; setBusy(true); setError("");
    try {
      if (item.status === "completed") { setSummary(await getPracticeResult(accessToken, item.id)); setAttempt(null); }
      else {
        const data = await getPracticeAttempt(accessToken, item.id);
        if (data.status === "completed") { setSummary(await getPracticeResult(accessToken, item.id)); setAttempt(null); }
        else {
          setAttempt(data); setSummary(null); setSubjectSlug(data.subject_slug); setTopicSlug(data.topic_slug ?? "");
          setMode(data.question_mode === "similar" ? "similar" : "fresh");
          setAnswers(Object.fromEntries(data.answers.map((a) => [a.question_id, a.selected_index])));
          setMarked(Object.fromEntries(data.answers.map((a) => [a.question_id, a.marked_for_review])));
          setCurrent(Math.min(data.current_position ?? 0, data.questions.length - 1)); setRemaining(Math.max(0, data.duration_seconds - data.elapsed_seconds)); setPaused(true); setPreview(true); timedOut.current = false;
        }
      }
      setTab("practice");
    } catch (e) { setError(message(e)); }
    finally { mutation.current = false; setBusy(false); }
  };
  const next = () => {
    if (mutation.current || paused || !attempt) return;
    const position = Math.min(current + 1, attempt.questions.length - 1);
    setCurrent(position); setError(""); setSaveStatus("Saving…");
    // Questions are already in memory. Save in order, without blocking navigation.
    void persist(false, position).then(() => setSaveStatus("Answers saved"))
      .catch(() => setSaveStatus("Not saved yet — reconnect to retry"));
  };
  const moreHistory = async () => {
    if (!accessToken || historyLoading) return;
    setHistoryLoading(true); setHistoryError("");
    try { const data = await getPracticeHistory(accessToken, history.length); setHistory((items) => [...items, ...data.items.filter((item) => !items.some((existing) => existing.id === item.id))]); setHistoryMore(data.has_more); }
    catch (e) { setHistoryError(message(e)); } finally { setHistoryLoading(false); }
  };

  return <main className={[s.workspace, active || openingSet ? s.live : ""].join(" ")}>
    <header className={s.header}>
      <div className={s.headingGroup}>
        <GraduationCap size={22} aria-hidden="true" />
        <h1>{dailyTask ? "Today’s topic quiz" : "Subjects"}</h1>
      </div>
      {dailyTask ? <Link className={s.secondary} href="/progress#today" onClick={event => { if (openingSet) cancelOpening(); else if (busy || active) { event.preventDefault(); if (!busy) void returnToPlan(); } }}><ArrowLeft size={14} /> Today’s plan</Link> : <div className={s.tabs} aria-label="Subject practice view"><button aria-pressed={tab === "practice"} disabled={busy} onClick={() => setTab("practice")}>Practise</button><button aria-pressed={tab === "history"} disabled={busy} onClick={() => void leave(undefined, undefined, "history")}><History size={15} /> History</button></div>}
    </header>
    {openingSet ? <><PracticeQuestionSkeleton {...openingSet} delayed={openingDelayed} /><div className={s.openingActions}><button className={s.secondary} onClick={cancelOpening}>Cancel preparation</button><span>Your timer starts only when the questions are ready.</span></div></> : <>
    {!dailyTask && !attempt && !summary && tab === "practice" && <PreparationTarget />}
    {error && <div role="alert" className={s.error}>{error} <button className={s.secondary} disabled={busy} onClick={() => { if (!attempt && !summary && tab === "practice" && (dailyTask || subject && mode === "similar")) void start(); else { setCatalogVersion((v) => v + 1); setHistoryVersion((v) => v + 1); } }}>Retry</button></div>}
    {tab === "history" ? <section className={s.panel} aria-label="Practice history">
      <div className={s.sectionTitle}><h2>Your saved sets</h2><button disabled={historyLoading} onClick={() => setHistoryVersion((v) => v + 1)}>Refresh</button></div>
      <p className={s.muted}>Open the entire set to review your progress. Timers stay stopped until you choose Resume.</p>
      {historyError && <p role="alert" className={s.error}>{historyError}</p>}
      {!history.length && !historyLoading && !historyError && <div className={s.empty}>Your practice sessions will appear here.</div>}
      <div className={s.historyList}>{history.map((item) => <button key={item.id} disabled={busy} onClick={() => void openHistory(item)}>
        <span><strong>{item.subject}</strong><small>{item.topic || "Mixed topics"} · {new Date(item.started_at).toLocaleDateString()}{item.question_mode === "similar" ? " · Similar practice" : ""}</small><small>{clock(item.duration_seconds)} spent · {item.total_questions} questions</small></span>
        <span><strong>{item.status === "completed" ? item.correct_answers + "/" + item.total_questions + " correct" : item.answered_questions + "/" + item.total_questions + " answered"}</strong><small>{item.status === "completed" ? "Review result" : "Review saved set"} <ArrowRight size={12} /></small></span>
      </button>)}</div>
      {historyLoading && <p role="status" className={s.muted}>Loading saved sets…</p>}
      {historyMore && <button className={s.secondary} disabled={historyLoading} onClick={() => void moreHistory()}>Load more sets</button>}
    </section> : summary ? <>
      <section className={s.panel}>
        <div className={s.sectionTitle}><div><span className={s.eyebrow}><Check size={14} /> Completed · saved to history</span><h2>{summary.subject} results</h2><p className={s.muted}>{summary.topic || "Mixed topics"} · {clock(summary.duration_seconds)} spent</p></div>{dailyTask ? <Link className={s.primary} href="/progress#today">Back to today’s plan <ArrowRight size={15} /></Link> : <button className={s.primary} onClick={() => void leave()}>New set <ArrowRight size={15} /></button>}</div>
        {dailyTask && <p className={s.muted}>{summary.answered_questions === summary.total_questions ? "Your quiz answers are saved to today’s target." : "Your answers are saved. Return to today’s plan to practise the remaining questions."}</p>}
        <div className={s.stats}><div><strong>{summary.score}/{summary.total_questions}</strong><small>Net practice score</small></div><div><strong>{summary.correct_answers}</strong><small>Correct</small></div><div><strong>{summary.answered_questions - summary.correct_answers}</strong><small>Incorrect</small></div><div><strong>{summary.total_questions - summary.answered_questions}</strong><small>Skipped</small></div></div>
        {summary.question_mode === "similar" && <p className={s.muted}>AI-created practice, not exam questions. Check the explanations; these answers are not an official key.</p>}
        {summary.correct_answers < summary.total_questions && <Link className={s.secondary} href="/mistake-notebook"><BookOpen size={15} /> Revise wrong &amp; skipped questions <ArrowRight size={14} /></Link>}
        <p className={s.muted}>{summary.negative_mark_fraction ? "+1 correct · −⅓ incorrect · 0 skipped. Normalized practice points, not an official exam score." : "Legacy set: +1 correct, no negative marking."}</p>
      </section>
      <section aria-label="Answer review"><h2 className={s.reviewTitle}>All {summary.total_questions} questions</h2>
        {summary.review.map((item) => <article className={s.review} key={item.question_id}>
          <div className={s.sectionTitle}><span className={s.eyebrow}>Question {item.position} · {item.topic}</span><span className={item.is_correct ? s.correctText : item.selected_index === null ? s.muted : s.wrongText}>{item.selected_index === null ? "Not attempted" : item.is_correct ? "Attempted · correct" : "Attempted · incorrect"}</span></div>
          {item.context && <p className={s.context}><QuestionText text={item.context} /></p>}<h3><QuestionText text={item.prompt} /></h3>
          <div className={s.options}>{item.options.map((option, i) => <div key={i} className={[s.option, i === item.correct_index ? s.correct : i === item.selected_index ? s.wrong : ""].join(" ")}><span>{String.fromCharCode(65+i)}</span><div><QuestionText text={option} />{i === item.correct_index && <small>Correct answer</small>}{i === item.selected_index && <small>Your answer</small>}</div></div>)}</div>
          <p className={s.explanation}><QuestionText text={item.explanation} /></p><QuestionSource label={item.source_label} source={item.provenance} />
        </article>)}
      </section>
    </> : preview && attempt ? <>
      <section className={s.panel}>
        <div className={s.sectionTitle}><div><span className={s.eyebrow}>Saved set · read-only review</span><h2>{attempt.subject}</h2><p className={s.muted}>{Object.keys(answers).length} attempted · {attempt.questions.length - Object.keys(answers).length} unanswered · {clock(attempt.elapsed_seconds)} spent</p><p className={s.muted}>{clock(remaining)} remaining when you resume. No timer is running here.</p></div>
          <button className={s.primary} onClick={() => { setPreview(false); setPaused(false); }}>{remaining ? "Resume this set" : "Submit timed-out set"} <Play size={14} /></button>
        </div>
      </section>
      <section aria-label="All saved questions">
        <nav className={s.reviewNav} aria-label="Saved question navigator">{attempt.questions.map((q) => <a key={q.id} className={answers[q.id] !== undefined ? s.answered : ""} href={"#saved-" + q.id} aria-label={"Question " + q.position + (answers[q.id] !== undefined ? ", attempted" : ", unanswered")}>{q.position}</a>)}</nav>
        <p className={s.muted}>Filled numbers = attempted · outlined numbers = unanswered. Answer keys appear after submission.</p>
        {attempt.questions.map((item) => <article className={[s.review, answers[item.id] !== undefined ? s.attemptedReview : ""].join(" ")} id={"saved-" + item.id} key={item.id}>
          <div className={s.sectionTitle}><span className={s.eyebrow}>Question {item.position} · {item.topic}</span><span className={s.statusTag}>{answers[item.id] !== undefined ? "Attempted" : "Not attempted"}{marked[item.id] ? " · marked" : ""}</span></div>
          {item.context && <p className={s.context}><QuestionText text={item.context} /></p>}<h3><QuestionText text={item.prompt} /></h3>
          <div className={s.options}>{item.options.map((option, i) => <div key={i} className={[s.option, i === answers[item.id] ? s.selected : ""].join(" ")}><span>{String.fromCharCode(65+i)}</span><div><QuestionText text={option} />{i === answers[item.id] && <small>Your saved answer</small>}</div></div>)}</div>
          <QuestionSource label={item.source_label} source={item.provenance} />
        </article>)}
      </section>
    </> : <>
      {dailyTask ? <div className={s.dailyQuizContext}><span><Sparkles size={14} /> Today’s target</span><strong>{dailyTask.subject_name} · {dailyTask.topic_name}</strong><small>Answer this topic’s questions to update your daily plan.</small></div> : <div className={s.filters}>
        <label>Subject<select value={subject?.slug ?? ""} disabled={busy || !subjects.length} onChange={(e) => void leave(e.target.value)}>{!subjects.length && <option>Loading subjects…</option>}{target ? <><optgroup label={`${target.code} written subjects`}>{subjectGroups.required.map((item) => <option key={item.id} value={item.slug}>{item.name}</option>)}</optgroup>{subjectGroups.optional.length > 0 && <optgroup label={`Extra practice · not required for ${target.code}`}>{subjectGroups.optional.map((item) => <option key={item.id} value={item.slug}>{item.name} (optional)</option>)}</optgroup>}</> : subjects.map((item) => <option key={item.id} value={item.slug}>{item.name}</option>)}</select></label>
        <label>Topic<select value={topic?.slug ?? ""} disabled={busy || !subject} onChange={(e) => void leave(subject?.slug, e.target.value)}><option value="">All topics</option>{subject?.topics.filter((item) => mode === "similar" ? !item.slug.startsWith("current") : item.question_count > 0).map((item) => <option key={item.id} value={item.slug}>{item.name}</option>)}</select></label>
        {!active && <><label>Set size<select value={mode === "similar" ? Math.min(count, 50) : count} disabled={busy} onChange={(e) => setCount(Number(e.target.value))}>{practiceChoices(mode).map((n) => <option value={n} key={n}>{n} questions</option>)}</select></label><label>Practice type<select value={mode} disabled={busy} onChange={(e) => { const choice = e.target.value as PracticeMode; setMode(choice); setError(""); if (choice === "similar") { setCount((n) => Math.min(n, 50)); if (topicSlug.startsWith("current")) setTopicSlug(""); } }}><option value="fresh">Unanswered questions</option><option value="mixed">Mixed revision</option><option value="similar">Similar practice · AI</option></select></label></>}
        {active && <span className={s.filterNote}>Changing filters saves this set for later.</span>}
      </div>}
      {active && question ? <section className={s.session} aria-label="Practice session">
        <div className={s.sessionHeader}><span>Question <strong>{current + 1}</strong> / {attempt.questions.length}</span><div className={s.timer}><Clock3 size={15} /><span>{clock(remaining)}</span><button disabled={busy || remaining === 0} onClick={() => setPaused((p) => !p)} aria-label={paused ? "Resume timer" : "Pause timer"}>{paused ? <Play size={15} /> : <Pause size={15} />}</button></div><button className={s.leave} disabled={busy} onClick={() => dailyTask ? void returnToPlan() : void leave(undefined, undefined, "history")}>Save & leave</button></div>
        <nav className={s.palette} aria-label="Question navigator">{attempt.questions.map((q, i) => <button key={q.id} aria-label={"Question " + (i+1) + (answers[q.id] !== undefined ? ", answered" : ", unanswered") + (marked[q.id] ? ", marked" : "")} aria-current={i === current ? "step" : undefined} className={[answers[q.id] !== undefined ? s.answered : "", marked[q.id] ? s.flagged : ""].join(" ")} disabled={busy || paused} onClick={() => setCurrent(i)}>{i + 1}</button>)}</nav>
        <div className={s.sessionLegend}>{Object.keys(answers).length} answered · {attempt.questions.length - Object.keys(answers).length} unanswered · {Object.values(marked).filter(Boolean).length} marked</div>
        <div className={s.questionBody} ref={questionBody}>{paused ? <div className={s.empty}><Pause size={24} /><h2>Take a breather.</h2><p>The timer is paused.</p><button className={s.primary} onClick={() => setPaused(false)}>Resume practice</button></div> : <>
          <div className={s.sectionTitle}><span className={s.eyebrow}>{question.topic}</span><button className={s.mark} disabled={busy || answers[question.id] === undefined} aria-pressed={!!marked[question.id]} title="Select an answer, then mark it for review" onClick={() => setMarked((m) => ({ ...m, [question.id]: !m[question.id] }))}><Bookmark size={14} /> {marked[question.id] ? "Marked" : "Mark for review"}</button></div>
          {question.context && <p className={s.context}><QuestionText text={question.context} /></p>}<h2 className={s.prompt}><QuestionText text={question.prompt} /></h2>
          <div className={s.options} role="group" aria-label="Answer options">{question.options.map((option, i) => <button key={i} className={[s.option, answers[question.id] === i ? s.selected : ""].join(" ")} disabled={busy || remaining === 0} aria-pressed={answers[question.id] === i} onClick={() => { setAnswers((a) => ({ ...a, [question.id]: i })); setSaveStatus("Unsaved changes"); }}><span>{String.fromCharCode(65+i)}</span><div><QuestionText text={option} /></div>{answers[question.id] === i && <Check size={16} />}</button>)}</div>
          <QuestionSource label={question.source_label} source={question.provenance} hideKey />
          <p className={s.muted}>Answers are evaluated after submission. {attempt.negative_mark_fraction ? "+1 correct · −⅓ incorrect · 0 skipped." : "Legacy set: no negative marking."}</p>
        </>}</div>
        <footer className={s.footer}><button className={s.secondary} disabled={busy || paused || current === 0} onClick={() => setCurrent((i) => i - 1)}><ArrowLeft size={15} /> Previous</button><span className={s.saveStatus} role="status">{busy ? "Saving…" : saveStatus}</span><button className={current === attempt.questions.length - 1 || remaining === 0 ? s.primary : s.secondary} disabled={busy} onClick={() => void finish()}>Submit set</button>{current < attempt.questions.length - 1 && remaining > 0 && <button className={s.primary} disabled={busy || paused} onClick={() => void next()}>{answers[question.id] !== undefined ? "Save & next" : "Skip & next"}<ArrowRight size={15} /></button>}</footer>
      </section> : dailyTask ? <section className={[s.panel,s.start].join(" ")}><span className={s.startIcon}><Target size={28}/></span><h2>Check today’s topic.</h2><p>{dailyTask.topic_name} · 50 questions · {clock(50 * (subjectSlug === "elementary-mathematics" ? 72 : 60))}</p><p className={s.muted}>CDS-style practice with relevant PYQs when available. Your answers and result stay saved.</p><button className={s.primary} disabled={busy || !accessToken} onClick={()=>void start()}>{dailyTask.quiz_status === "in_progress" ? "Resume quiz" : "Start 50-question quiz"}<ArrowRight size={16}/></button></section> : <section className={[s.panel, s.start].join(" ")}>
        <span className={s.startIcon}><Target size={28} /></span><h2>Ready to practise?</h2>
        <p>{topic?.name || subject?.name || "Choose a subject"} · {target ? isExtraPractice ? `Extra practice · not required for ${target.code}` : `${target.code} preparation` : subjectSlug === "elementary-mathematics" ? "CDS Maths · not required for OTA" : "CDS / OTA"}</p>
        {pool || mode === "similar" ? <><div className={s.setFacts}><span><strong>{setSize}</strong> questions in this set</span><span><strong>{clock(setSize * (subjectSlug === "elementary-mathematics" ? 72 : 60))}</strong> practice time</span>{mode !== "similar" && <span><strong>{pool?.unseen}</strong> not yet answered</span>}</div>
          {mode === "similar" ? <p className={s.muted}>New CDS-style questions with explanations. AI-created, not actual exam questions.</p> : mode === "mixed" ? <p className={s.muted}>A shuffled set, including questions you’ve answered before.</p> : !!setSize && setSize < count && <p className={s.muted}>{setSize} unanswered questions in this selection. Want a full {Math.min(count, 50)}-question set? Create similar practice below.</p>}
        </> : <p className={s.muted}>{accessToken ? "Loading your questions…" : "Sign in to save your practice."}</p>}
          {!!setSize && <button className={s.primary} disabled={busy || !accessToken || !subject} onClick={() => void start()}>{busy ? "Preparing your set…" : mode === "similar" ? `Create ${setSize} similar questions` : `Start ${setSize}-question set`}{mode === "similar" ? <Sparkles size={16} /> : <ArrowRight size={16} />}</button>}
          {mode !== "similar" && pool && setSize < count && <>
            {!setSize && <p className={s.muted}>{pool.total ? "No unanswered bank questions in this selection. Keep practising with a new similar set or mixed revision." : "This topic’s question bank is still growing. You can create a similar practice set now."}</p>}
            <div className={s.continuePractice}><button className={s.secondary} disabled={busy || !accessToken || topicSlug.startsWith("current")} onClick={() => void start("similar")}><Sparkles size={15} /> Create {Math.min(count, 50)} similar questions</button>{mode === "fresh" && !!pool.total && <button className={s.secondary} disabled={busy} onClick={() => void start("mixed")}>Start mixed revision <ArrowRight size={15} /></button>}</div>
          </>}
      </section>}
    </>}
    </>}
  </main>;
}

// Only the explicitly supported emphasis tag is rendered; source HTML is never injected.
function QuestionText({ text }: { text: string }) {
  return <>{text.split(/(<u>[\s\S]*?<\/u>)/g).map((part, i) => part.startsWith("<u>") ? <u key={i}>{part.slice(3, -4)}</u> : part)}</>;
}
function QuestionSource({ label, source, hideKey = false }: { label: string; source: PracticeProvenance | null; hideKey?: boolean }) {
  return <div className={s.source}><small>{label}</small>{source?.kind === "pyq" && <>
    <div><a href={source.source_page_url} target="_blank" rel="noreferrer">Original page ↗</a><a href={source.source_url} target="_blank" rel="noreferrer">Question paper ↗</a>{!hideKey && source.answer_key_url && <a href={source.answer_key_url} target="_blank" rel="noreferrer">{source.answer_basis === "provisional" ? "Provisional key" : "Official key"} ↗</a>}</div>
  </>}</div>;
}
