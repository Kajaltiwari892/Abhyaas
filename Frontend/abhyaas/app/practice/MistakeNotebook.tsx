"use client";

import { ArrowLeft, ArrowRight, BookOpen, Check, ChevronDown, ExternalLink, RotateCcw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../components/AuthProvider";
import { subjectsQuery } from "@/lib/study-api";
import { finishRevision, notebookQuery, getRevision, getRevisionResult, saveRevision, startRevision, type NotebookFilters, type RevisionQuestion, type RevisionResult, type RevisionReview, type RevisionSession } from "@/lib/notebook-api";
import QuestionText from "./NotebookText";
import MistakeNote from "./MistakeNote";
import s from "./notebook.module.css";

const notebookUrl = "/mistake-notebook";
const sessionUrl = (id: string) => `${notebookUrl}?revision=${encodeURIComponent(id)}`;
const message = (error: unknown) => error instanceof Error ? error.message : "Couldn't load your notebook. Please try again.";

export default function MistakeNotebook({ revisionId = "" }: { revisionId?: string }) {
  const { accessToken } = useAuth();
  const router = useRouter();
  const { data: subjects = [] } = useQuery(subjectsQuery());
  const [filters, setFilters] = useState<NotebookFilters>({ subject: "", reason: "all", state: "pending", offset: 0 });
  const [version, setVersion] = useState(0);
  const notebook = useQuery({ ...notebookQuery(accessToken, filters), enabled: !!accessToken && !revisionId });
  const [opened, setOpened] = useState<{ id: string; session: RevisionSession; result?: RevisionResult }>();
  const [loadError, setLoadError] = useState<{ key: string; message: string }>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [count, setCount] = useState(5);
  const mutation = useRef(false);
  const loadKey = `${revisionId}:${JSON.stringify(filters)}:${version}`;
  const page = notebook.data;
  const open = opened?.id === revisionId ? opened : undefined;
  const failed = revisionId ? (loadError?.key === loadKey ? loadError.message : "") : notebook.error?.message ?? "";
  const loading = revisionId ? !open && !failed : !page && !failed;
  const revisionCount = Math.min(count, page?.revision_available ?? count);
  const revisionSizes = [...new Set([5, 10, 20].map((size) => Math.min(size, page?.revision_available ?? size)))].filter((size) => size > 0);
  const filtered = !!filters.subject || filters.reason !== "all";

  useEffect(() => {
    if (!accessToken || !revisionId) return;
    const controller = new AbortController();
    const load = async () => {
      try {
        if (revisionId) {
          const session = await getRevision(accessToken, revisionId, controller.signal);
          const result = session.status === "completed" ? await getRevisionResult(accessToken, revisionId, controller.signal) : undefined;
          if (!controller.signal.aborted) setOpened((old) => old?.id === revisionId && old.result && !result ? old : { id: revisionId, session, result });
        }
      } catch (reason) {
        if (!controller.signal.aborted) setLoadError({ key: loadKey, message: message(reason) });
      }
    };
    void load();
    return () => controller.abort();
  }, [accessToken, revisionId, filters, loadKey]);

  const change = (patch: Partial<NotebookFilters>) => { setError(""); setFilters((old) => ({ ...old, ...patch, offset: 0 })); };
  const start = async () => {
    if (!accessToken || mutation.current) return;
    mutation.current = true; setBusy(true); setError("");
    try {
      const session = await startRevision(accessToken, filters.subject, filters.reason, revisionCount);
      setOpened({ id: session.id, session });
      router.push(sessionUrl(session.id));
    } catch (reason) { setError(message(reason)); }
    finally { mutation.current = false; setBusy(false); }
  };

  if (revisionId && open) return <main className={s.workspace}>
    {open.result ? <>
      <header className={s.header}><div><Link className={s.back} href={notebookUrl}><ArrowLeft size={15} /> Notebook</Link><h1>Revision complete</h1></div><span className={s.badge}><Check size={14} /> Saved</span></header>
      <section className={s.result} aria-label="Revision result">
        <h2>A little stronger than before.</h2><p>Correct answers move to “Revised”. The rest stay in “To revisit”. Your earlier mistakes stay saved as notes.</p>
        <div className={s.stats}><div><strong>{open.result.correct_answers}</strong><span>Correct</span></div><div><strong>{open.result.wrong_answers}</strong><span>Incorrect</span></div><div><strong>{open.result.skipped_questions}</strong><span>Skipped</span></div></div>
        <Link className={s.primary} href={notebookUrl}>Back to notebook <ArrowRight size={15} /></Link>
        <small>Your original paper and practice scores are unchanged.</small>
      </section>
      <h2 className={s.reviewHeading}>Your answers</h2>
      {open.result.review.map((item, i) => <ReviewCard key={item.question_key} question={item} number={i + 1} />)}
    </> : <RevisionWorkspace key={open.session.id} session={open.session} onComplete={(result) => { setOpened({ ...open, result });  }} />}
  </main>;

  return <main className={`${s.workspace} ${s.notesWorkspace}`}>
    <header className={s.header}><div><Link className={s.back} href="/subjects"><ArrowLeft size={15} /> Back to subjects</Link><h1>Mistake notebook</h1></div><span className={s.notebookMark}><BookOpen size={23} /></span></header>
    {!revisionId && <>
      <p className={s.intro}>Your mistakes, turned into revision notes. Read the correction, then give it another go.</p>
      <div className={s.toolbar}>
        <div className={s.tabs} aria-label="Notebook view"><button disabled={busy} aria-pressed={filters.state === "pending"} onClick={() => change({ state: "pending" })}>To revisit <span>{page?.counts.pending ?? "—"}</span></button><button disabled={busy} aria-pressed={filters.state === "resolved"} onClick={() => change({ state: "resolved" })}>Revised <span>{page?.counts.resolved ?? "—"}</span></button></div>
        <label className={s.filter}>Subject<select disabled={busy} value={filters.subject} onChange={(e) => change({ subject: e.target.value })}><option value="">All subjects</option>{subjects.map((subject) => <option key={subject.slug} value={subject.slug}>{subject.name}</option>)}</select></label>
        <label className={s.filter}>Show<select disabled={busy} value={filters.reason} onChange={(e) => change({ reason: e.target.value as NotebookFilters["reason"] })}><option value="all">All notes</option><option value="wrong">Incorrect answers</option><option value="skipped">Left unanswered</option></select></label>
      </div>
    </>}
    {loading && <div className={s.skeleton} role="status" aria-live="polite"><span className={s.srOnly}>Opening your revision notes…</span><div aria-hidden="true" /><div aria-hidden="true" /></div>}
    {failed && <div className={s.error} role="alert">{failed}<button className={s.secondary} onClick={() => revisionId ? setVersion((v) => v + 1) : void notebook.refetch()}>Retry</button></div>}
    {error && <p className={s.error} role="alert">{error}</p>}
    {!revisionId && page && <>
      {(page.active_session || filters.state === "pending" && page.revision_available > 0) && <section className={s.revisionBar} aria-label="Try your notebook questions again"><span className={s.revisionIcon}><RotateCcw size={18} /></span><div><h2>{page.active_session ? "Continue your revision" : "Ready to try again?"}</h2><p>{page.active_session ? "Your answers are saved. Pick up where you left off." : "A short, untimed quiz from your notebook."}</p></div>
        {page.active_session ? <Link className={s.primary} href={sessionUrl(page.active_session.id)}>Continue <ArrowRight size={15} /></Link> : <div className={s.startControls}><label className={s.srOnly} htmlFor="revision-size">Number of questions to retry</label><select id="revision-size" value={revisionCount} disabled={busy} onChange={(e) => setCount(Number(e.target.value))}>{revisionSizes.map((size) => <option key={size} value={size}>{size} {size === 1 ? "question" : "questions"}</option>)}</select><button className={s.primary} disabled={busy} onClick={() => void start()}>{busy ? "Opening…" : "Try again"}<ArrowRight size={15} /></button></div>}
      </section>}
      {!page.items.length ? <section className={s.empty}><span className={s.revisionIcon}>{page.counts.total ? <Check size={24} /> : <BookOpen size={24} />}</span><h2>{filters.offset ? "You’ve reached the end of these notes" : filtered ? "No notes match these filters" : filters.state === "resolved" ? "Your revised notes will appear here" : page.counts.total && !page.counts.pending ? "You’re caught up" : "Your notebook starts here"}</h2><p>{filters.offset ? "Go back to the first page to review them again." : filtered ? "Try all subjects or all notes to find what you’d like to review." : filters.state === "resolved" ? "Answer a question correctly on another attempt and its note moves here. The earlier mistake stays saved." : page.counts.total ? "You’ve answered these questions correctly on another attempt. Their notes are saved under Revised." : "Finish a practice set or paper. Questions to revisit and those left unanswered will be saved here automatically."}</p>{filters.offset ? <button className={s.secondary} onClick={() => change({ offset: 0 })}>Back to first page</button> : filtered ? <button className={s.secondary} onClick={() => change({ subject: "", reason: "all" })}>Clear filters</button> : filters.state === "resolved" || page.counts.total ? <button className={s.secondary} onClick={() => change({ state: filters.state === "resolved" ? "pending" : "resolved" })}>{filters.state === "resolved" ? "View notes to revisit" : "Read revised notes"} <ArrowRight size={14} /></button> : <Link className={s.secondary} href="/subjects">Start practising <ArrowRight size={14} /></Link>}</section> : <>
        <div className={s.listHeading}><span>{filters.state === "pending" ? "Your revision notes" : "Revised notes · keep them for a quick recap"}</span><small>{filters.offset + 1}–{filters.offset + page.items.length} of {page.total}</small></div>
        <div className={s.entries}>{page.items.map((item, i) => <MistakeNote key={item.question_key} item={item} number={filters.offset + i + 1} />)}</div>
        {(page.has_more || filters.offset > 0) && <nav className={s.pagination} aria-label="Notebook pages"><button className={s.secondary} disabled={!filters.offset} onClick={() => setFilters((old) => ({ ...old, offset: Math.max(0, old.offset - 20) }))}><ArrowLeft size={14} /> Previous notes</button><button className={s.secondary} disabled={!page.has_more} onClick={() => setFilters((old) => ({ ...old, offset: old.offset + 20 }))}>Next notes <ArrowRight size={14} /></button></nav>}
      </>}
      {!!page.recent_sessions.length && <details className={s.recent}><summary>Recent revision <ChevronDown size={14} /></summary><div>{page.recent_sessions.map((session) => <Link key={session.id} href={sessionUrl(session.id)}><span>{new Date(session.completed_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })} · {session.total_questions} questions</span><span>{session.correct_answers} correct <ArrowRight size={13} /></span></Link>)}</div></details>}
    </>}
  </main>;
}

export function RevisionWorkspace({ session, onComplete }: { session: RevisionSession; onComplete: (result: RevisionResult) => void }) {
  const { accessToken } = useAuth();
  const router = useRouter();
  const [answers, setAnswers] = useState(session.answers);
  const [current, setCurrent] = useState(session.current_position);
  const [busy, setBusy] = useState(false);
  const [confirmFinish, setConfirmFinish] = useState(false);
  const [error, setError] = useState("");
  const [saveStatus, setSaveStatus] = useState("Your answers are saved as you go");
  const mutation = useRef(false);
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const latest = useRef<(() => Promise<unknown>) | null>(null);
  const questionBody = useRef<HTMLDivElement>(null);
  const question = session.questions[current];
  const answered = Object.values(answers).filter((value) => value !== null).length;
  const skipped = session.questions.length - answered;

  const persist = useCallback((keepalive = false) => {
    if (!accessToken) return Promise.reject(new Error("Please sign in to save your revision."));
    const saving = queue.current.catch(() => {}).then(() => saveRevision(accessToken, session.id, current, answers, keepalive));
    queue.current = saving;
    return saving;
  }, [accessToken, session.id, current, answers]);

  useEffect(() => { latest.current = () => persist(true); }, [persist]);
  useEffect(() => {
    if (busy) return;
    let alive = true;
    const timer = window.setTimeout(() => {
      if (mutation.current) return;
      setSaveStatus("Saving…");
      void persist().then(() => { if (alive) setSaveStatus("Answers saved"); }).catch(() => { if (alive) setSaveStatus("Not saved — use Save & next to retry"); });
    }, 600);
    return () => { alive = false; window.clearTimeout(timer); };
  }, [persist, busy]);
  useEffect(() => {
    const save = () => { if (!mutation.current) void latest.current?.().catch(() => {}); };
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("pagehide", save); window.addEventListener("beforeunload", warn);
    return () => { window.removeEventListener("pagehide", save); window.removeEventListener("beforeunload", warn); save(); };
  }, []);
  useEffect(() => { questionBody.current?.scrollTo({ top: 0 }); }, [current]);

  const savedAction = async (action: () => void) => {
    if (mutation.current) return;
    mutation.current = true; setBusy(true); setError("");
    try { await persist(); setSaveStatus("Answers saved"); action(); }
    catch (reason) { setError(message(reason)); }
    finally { mutation.current = false; setBusy(false); }
  };
  const finish = async () => {
    if (!accessToken || mutation.current) return;
    mutation.current = true; setBusy(true); setError("");
    try {
      await queue.current.catch(() => {});
      const result = await finishRevision(accessToken, session.id, current, answers);
      latest.current = null;
      onComplete(result);
    } catch (reason) { setError(message(reason)); }
    finally { mutation.current = false; setBusy(false); }
  };

  return <div className={s.live}>
    <header className={s.header}><div><button className={s.back} disabled={busy} onClick={() => void savedAction(() => router.push(notebookUrl))}><ArrowLeft size={15} /> Save &amp; leave</button><h1>Quick revision</h1></div><span className={s.badge}>No timer</span></header>
    {error && <p className={s.error} role="alert">{error}</p>}
    <section className={s.session} aria-label="Revision questions">
      <div className={s.sessionHeader}><span>Question {current + 1} of {session.questions.length}</span><small>{answered} answered</small></div>
      <nav className={s.palette} aria-label="Choose a revision question">{session.questions.map((item, i) => <button key={item.question_key} aria-label={`Question ${i + 1}${answers[item.question_key] != null ? ", answered" : ", not answered"}`} aria-current={current === i ? "step" : undefined} className={answers[item.question_key] != null ? s.answered : ""} disabled={busy} onClick={() => setCurrent(i)}>{i + 1}</button>)}</nav>
      <div className={s.questionBody} ref={questionBody}>
        <span className={s.caption}>{question.subject} · {question.topic}</span>
        {question.context && <div className={s.context}><QuestionText text={question.context} /></div>}
        <h2 className={s.prompt}><QuestionText text={question.prompt} /></h2>
        <div className={s.options} role="group" aria-label="Answer options">{question.options.map((option, i) => <button key={i} className={`${s.option} ${answers[question.question_key] === i ? s.selected : ""}`} aria-pressed={answers[question.question_key] === i} disabled={busy} onClick={() => setAnswers((old) => ({ ...old, [question.question_key]: i }))}><span>{String.fromCharCode(65 + i)}</span><div><QuestionText text={option} /></div>{answers[question.question_key] === i && <Check size={16} />}</button>)}</div>
        <button className={s.clear} disabled={busy || answers[question.question_key] == null} onClick={() => setAnswers((old) => ({ ...old, [question.question_key]: null }))}>Clear choice</button>
        <Sources question={question} />
      </div>
      <div className={s.footer}><small role="status">{saveStatus}</small><button className={s.secondary} disabled={busy || current === 0} onClick={() => setCurrent((i) => i - 1)}><ArrowLeft size={14} /> Back</button>{current < session.questions.length - 1 && <button className={s.primary} disabled={busy} onClick={() => void savedAction(() => setCurrent((i) => i + 1))}>Save &amp; next <ArrowRight size={14} /></button>}<button className={current === session.questions.length - 1 ? s.primary : s.secondary} disabled={busy} onClick={() => skipped ? setConfirmFinish(true) : void finish()}>{busy ? "Saving…" : "Finish revision"}</button></div>
    </section>
    {confirmFinish && <div className={s.confirm} role="alert"><span>{skipped} {skipped === 1 ? "question is" : "questions are"} still unanswered. Finish anyway?</span><button className={s.secondary} disabled={busy} onClick={() => setConfirmFinish(false)}>Keep revising</button><button className={s.primary} disabled={busy} onClick={() => void finish()}>Finish</button></div>}
  </div>;
}

function ReviewCard({ question, number }: { question: RevisionReview; number: number }) {
  return <article className={s.review}><div className={s.reviewMeta}><span>Question {number} · {question.topic}</span><span>{question.selected_index === null ? "Skipped" : question.is_correct ? "Correct" : "Incorrect"}</span></div><h3 className={s.prompt}><QuestionText text={question.prompt} /></h3><AnswerReview question={question} /><Sources question={question} /></article>;
}

function AnswerReview({ question }: { question: RevisionReview }) {
  return <>{question.context && <div className={s.context}><QuestionText text={question.context} /></div>}<div className={s.reviewOptions}>{question.options.map((option, i) => <div key={i} className={i === question.correct_index ? s.correct : i === question.selected_index ? s.wrong : ""}><span>{String.fromCharCode(65 + i)}.</span><span><QuestionText text={option} /></span>{i === question.correct_index ? <small>Correct answer</small> : i === question.selected_index ? <small>Your answer</small> : null}</div>)}</div>{question.explanation && <p className={s.explanation}><QuestionText text={question.explanation} /></p>}</>;
}

function Sources({ question }: { question: RevisionQuestion }) {
  return <div className={s.sources}>{question.source_page_url && <a href={question.source_page_url} target="_blank" rel="noreferrer">Original question <ExternalLink size={12} /></a>}{question.source_url && <a href={question.source_url} target="_blank" rel="noreferrer">Original paper <ExternalLink size={12} /></a>}</div>;
}
