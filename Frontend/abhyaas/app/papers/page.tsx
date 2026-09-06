"use client";

import { ArrowLeft, ArrowRight, Bookmark, Calendar, Check, Clock3, ExternalLink, FileCheck2, FileText, ShieldCheck, X } from "lucide-react";
import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import AppShell from "../components/AppShell";
import { useAuth } from "../components/AuthProvider";
import PrimaryButton from "@/components/ui/primary-button";
import { ApiError } from "@/lib/auth-api";
import { completePaperAttempt, getPaper, getPapers, savePaperAnswer, startPaperAttempt, type PaperAttempt, type PaperAttemptSummary, type PaperDetail, type PaperListItem } from "@/lib/study-api";

type PaperMode = "review" | "mock" | "summary" | null;
const PAPER_YEARS = [2026, 2025, 2024] as const;
const formatTime = (seconds: number) => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
const messageFor = (reason: unknown, fallback: string) => reason instanceof ApiError ? reason.message : fallback;

export default function PapersPage() {
  const { accessToken } = useAuth();
  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [year, setYear] = useState("");
  const [cycle, setCycle] = useState("");
  const [subject, setSubject] = useState("");
  const [mode, setMode] = useState<PaperMode>(null);
  const [detail, setDetail] = useState<PaperDetail | null>(null);
  const [attempt, setAttempt] = useState<PaperAttempt | null>(null);
  const [summary, setSummary] = useState<PaperAttemptSummary | null>(null);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [marked, setMarked] = useState<Record<string, boolean>>({});
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const [remaining, setRemaining] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    getPapers({ year: year ? Number(year) : undefined, cycle: cycle || undefined, subject: subject || undefined })
      .then(data => { if (!cancelled) { setPapers(data); setError(""); } })
      .catch((reason: unknown) => { if (!cancelled) setError(messageFor(reason, "The paper archive could not be loaded.")); });
    return () => { cancelled = true; };
  }, [cycle, subject, year]);

  const closeWorkspace = useCallback(() => {
    if (busy) return;
    setMode(null); setDetail(null); setAttempt(null); setSummary(null); setCurrent(0); setAnswers({}); setMarked({}); setRevealed({}); setError("");
  }, [busy]);

  useEffect(() => {
    if (!mode) return;
    const handleKey = (event: KeyboardEvent) => { if (event.key === "Escape") closeWorkspace(); };
    document.body.classList.add("paper-dialog-open");
    window.addEventListener("keydown", handleKey);
    return () => { document.body.classList.remove("paper-dialog-open"); window.removeEventListener("keydown", handleKey); };
  }, [closeWorkspace, mode]);

  useEffect(() => {
    if (mode !== "mock" || !attempt || remaining <= 0) return;
    const timer = window.setInterval(() => setRemaining(value => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [attempt, mode, remaining]);

  const openReview = async (paper: PaperListItem) => {
    if (!accessToken) return;
    setBusy(true); setError("");
    try { setDetail(await getPaper(accessToken, paper.id)); setCurrent(0); setAnswers({}); setRevealed({}); setMode("review"); }
    catch (reason) { setError(messageFor(reason, "The official paper could not be opened.")); }
    finally { setBusy(false); }
  };

  const openMock = async (paper: PaperListItem) => {
    if (!accessToken) return;
    setBusy(true); setError("");
    try {
      const [next, paperDetail] = await Promise.all([
        startPaperAttempt(accessToken, paper.id),
        getPaper(accessToken, paper.id),
      ]);
      setAttempt(next); setDetail(paperDetail); setRemaining(next.duration_seconds); setAnswers({}); setMarked({}); setRevealed({}); setCurrent(0); setSummary(null); setMode("mock");
    } catch (reason) { setError(messageFor(reason, "The timed paper could not be started.")); }
    finally { setBusy(false); }
  };

  const submitMock = useCallback(async () => {
    if (!accessToken || !attempt || busy) return;
    setBusy(true); setError("");
    try {
      const elapsed = Math.max(0, attempt.duration_seconds - remaining);
      const submittedAnswers = Object.entries(answers).map(([questionId, selectedIndex]) => ({
        question_id: questionId,
        selected_index: selectedIndex,
        marked_for_review: Boolean(marked[questionId]),
      }));
      setSummary(await completePaperAttempt(accessToken, attempt.id, elapsed, submittedAnswers));
      setMode("summary");
    } catch (reason) { setError(messageFor(reason, "The paper could not be submitted.")); }
    finally { setBusy(false); }
  }, [accessToken, answers, attempt, busy, marked, remaining]);

  const saveAndMove = async () => {
    const question = attempt?.questions[current];
    const selected = question ? answers[question.id] : undefined;
    if (!accessToken || !attempt || !question || selected === undefined) return;
    setBusy(true); setError("");
    try {
      await savePaperAnswer(accessToken, attempt.id, question.id, { selected_index: selected, marked_for_review: Boolean(marked[question.id]) });
      if (current < attempt.questions.length - 1) setCurrent(index => index + 1);
      else {
        const elapsed = Math.max(0, attempt.duration_seconds - remaining);
        const submittedAnswers = Object.entries(answers).map(([questionId, selectedIndex]) => ({
          question_id: questionId,
          selected_index: selectedIndex,
          marked_for_review: Boolean(marked[questionId]),
        }));
        setSummary(await completePaperAttempt(accessToken, attempt.id, elapsed, submittedAnswers));
        setMode("summary");
      }
    } catch (reason) { setError(messageFor(reason, "Your answer could not be saved.")); }
    finally { setBusy(false); }
  };

  const reviewQuestion = mode === "review" ? detail?.questions[current] : undefined;
  const activeQuestion = reviewQuestion ?? attempt?.questions[current];
  const solutionQuestion = activeQuestion
    ? detail?.questions.find(question => question.id === activeQuestion.id)
    : undefined;
  const selected = activeQuestion ? answers[activeQuestion.id] : undefined;
  const answeredCount = Object.keys(answers).length;
  const totalAttemptQuestions = attempt?.questions.length ?? 0;

  return <AppShell active="Previous papers"><main className="workspace papers-workspace">
    <header className="workspace-header"><div><span className="workspace-kicker">Learn from the real examination</span><h1>Previous papers</h1><p>Complete official UPSC papers, with verified answers clearly distinguished from questions still being reviewed.</p></div><div className="workspace-badge"><FileCheck2 size={15} /> Official archive</div></header>
    <section className="paper-filters">
      <label><Calendar size={15} /><select aria-label="Filter by year" value={year} onChange={event => setYear(event.target.value)}><option value="">All years</option>{PAPER_YEARS.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      <label><ShieldCheck size={15} /><select aria-label="Filter by cycle" value={cycle} onChange={event => setCycle(event.target.value)}><option value="">Both cycles</option><option value="I">CDS I</option><option value="II">CDS II</option></select></label>
      <label><FileText size={15} /><select aria-label="Filter by subject" value={subject} onChange={event => setSubject(event.target.value)}><option value="">All subjects</option><option value="english">English</option><option value="general-knowledge">General Knowledge</option><option value="elementary-mathematics">Elementary Mathematics</option></select></label>
      <span>{papers.length} official {papers.length === 1 ? "paper" : "papers"}</span>
    </section>
    {error && !mode && <p className="workspace-message is-error">{error}</p>}
    <section className="paper-type-grid">{papers.map((paper, index) => <article key={paper.id}>
      <header><span>{String(index + 1).padStart(2, "0")}</span><FileText size={23} /></header>
      <small>CDS {paper.cycle} · {paper.year} · {paper.academy_tracks.join(" · ")}</small>
      <h2>{paper.subject_name}</h2>
      <p>All {paper.available_question_count} official questions are available to solve. {paper.verified_question_count} currently have an official or verified answer key for scoring.</p>
      <div className="paper-card-meta"><span><Clock3 size={13} /> {paper.duration_seconds / 3600} hours</span><span>{paper.total_marks} marks</span></div>
      <div className="paper-actions"><PrimaryButton size="sm" onClick={() => void openMock(paper)} disabled={busy || paper.available_question_count === 0}><Clock3 size={15} /> Solve &amp; score</PrimaryButton><button disabled={busy || !paper.solutions_available} onClick={() => void openReview(paper)}>Review answers <ArrowRight size={15} /></button></div>
      <a className="paper-source-link" href={paper.source_url} target="_blank" rel="noreferrer">Open official UPSC paper <ExternalLink size={12} /></a>
    </article>)}</section>
    {!papers.length && !error && <section className="paper-empty"><FileText size={25} /><h2>{year ? `No ${year} paper matches these filters.` : "No paper matches these filters."}</h2><p>{year ? `The ${year} archive will appear here as its official papers are imported.` : "Try another year, cycle, or subject."}</p><button onClick={() => { setYear(""); setCycle(""); setSubject(""); }}>Clear filters</button></section>}
    <section className="paper-method"><div><span className="workspace-kicker">Transparent by design</span><h2>Complete papers. Honest scoring.</h2></div><div><article><strong>01 · Full review</strong><p>Browse every official question in its original UPSC scan and retain the exact paper numbering.</p></article><article><strong>02 · Solve the paper</strong><p>Answer the complete timed paper. Marks use only published or independently verified answer keys.</p></article></div></section>
    {mode && <div className="paper-dialog-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) closeWorkspace(); }}>
      <section className="paper-dialog" role="dialog" aria-modal="true" aria-label={mode === "review" ? "Official paper review" : "Timed paper"}>
        <header className="paper-dialog-header"><div><small>{mode === "review" ? "Review mode" : mode === "summary" ? "Attempt complete" : "Timed mock"}</small><h2>{detail?.title ?? attempt?.title}</h2></div>{mode === "mock" && <strong><Clock3 size={15} /> {formatTime(remaining)}</strong>}<button aria-label="Close paper" onClick={closeWorkspace}><X size={19} /></button></header>
        {error && <p className="workspace-message is-error">{error}</p>}
        {mode === "summary" && summary ? <PaperSummary summary={summary} onClose={closeWorkspace} /> : activeQuestion && <><div className="paper-attempt-progress" aria-label={`${answeredCount} of ${totalAttemptQuestions} questions answered`}><div><span>{mode === "mock" ? `${answeredCount} answered` : "Paper review"}</span><small>{mode === "mock" ? `${totalAttemptQuestions - answeredCount} remaining` : `${detail?.questions.length ?? 0} questions`}</small></div><i><b style={{ width: `${mode === "mock" && totalAttemptQuestions ? answeredCount * 100 / totalAttemptQuestions : 100}%` }} /></i></div><div className="paper-question-layout">
          <aside aria-label="Question numbers">{(mode === "review" ? detail?.questions : attempt?.questions)?.map((question, index) => <button key={question.id} aria-label={`Open question ${question.number}`} className={`${current === index ? "active" : ""} ${answers[question.id] !== undefined ? "answered" : ""}`} onClick={() => setCurrent(index)}>{question.number}</button>)}</aside>
          <div className="paper-question-panel"><div className="paper-question-label"><span>Official question {activeQuestion.number}</span>{activeQuestion.topic && <small>{activeQuestion.topic}</small>}<small>{activeQuestion.is_verified ? "Verified key available" : "Official scan"}</small>{mode === "mock" && <button className={marked[activeQuestion.id] ? "marked" : ""} onClick={() => setMarked(values => ({ ...values, [activeQuestion.id]: !values[activeQuestion.id] }))}><Bookmark size={14} /> Mark for review</button>}</div><h3>{activeQuestion.prompt}</h3>{activeQuestion.context && <p>{activeQuestion.context}</p>}
            <div className={`paper-question-content ${activeQuestion.asset_url ? "has-scan" : ""}`}>
              <section className="paper-answer-panel" aria-label={`Answer question ${activeQuestion.number}`}><header><div><small>Answer for question {activeQuestion.number}</small><strong>Choose one option for this question only</strong></div><b>Select A, B, C or D</b></header><div className="paper-mcq-options">{activeQuestion.options.map((option, index) => { const answerIsRevealed = Boolean(revealed[activeQuestion.id]); const correct = Boolean(answerIsRevealed && solutionQuestion?.is_verified && solutionQuestion.correct_index === index); const incorrect = Boolean(answerIsRevealed && selected === index && solutionQuestion?.is_verified && solutionQuestion.correct_index !== index); return <button aria-pressed={selected === index} className={`${selected === index ? "selected" : ""} ${correct ? "correct" : ""} ${incorrect ? "incorrect" : ""}`} key={`${activeQuestion.id}-${index}`} onClick={() => { setAnswers(values => ({ ...values, [activeQuestion.id]: index })); setRevealed(values => ({ ...values, [activeQuestion.id]: false })); }}><span>{String.fromCharCode(65 + index)}</span>{option}{correct && <Check size={15} />}</button>; })}</div>
                {solutionQuestion?.is_verified && !revealed[activeQuestion.id] && <button className="paper-reveal-answer" onClick={() => setRevealed(values => ({ ...values, [activeQuestion.id]: true }))}>{selected === undefined ? "Reveal answer and explanation" : "Check answer and explanation"}</button>}
                {solutionQuestion?.is_verified && revealed[activeQuestion.id] && solutionQuestion.explanation ? <div className="paper-explanation"><small>{selected === solutionQuestion.correct_index ? "Correct answer" : "Official answer"}</small><p>{solutionQuestion.explanation}</p><span><FileCheck2 size={13} /> {solutionQuestion.source_label}</span></div> : solutionQuestion && !solutionQuestion.is_verified && <div className="paper-verification-note"><FileText size={15} /><div><strong>Explanation awaiting an official answer key</strong><p>Your choice is saved for question {activeQuestion.number}. Its answer and explanation will only be shown after a reliable key is available.</p></div></div>}
              </section>
              {activeQuestion.asset_url && <figure className="paper-question-scan"><figcaption><span>Official scan reference for question {activeQuestion.number}</span><a href={activeQuestion.asset_url} target="_blank" rel="noreferrer">Open full-size scan <ExternalLink size={11} /></a></figcaption><Image src={activeQuestion.asset_url} alt={`Official UPSC scan containing question ${activeQuestion.number}`} width={1286} height={1670} priority={current === 0} /></figure>}
            </div>
            <footer><button disabled={current === 0} onClick={() => setCurrent(index => index - 1)}><ArrowLeft size={15} /> Previous</button><span>{current + 1} / {(mode === "review" ? detail?.questions.length : attempt?.questions.length) ?? 0}</span>{mode === "review" ? <button disabled={current === (detail?.questions.length ?? 1) - 1} onClick={() => setCurrent(index => index + 1)}>Next <ArrowRight size={15} /></button> : <div><button onClick={() => void submitMock()} disabled={busy}>Submit</button><PrimaryButton size="sm" disabled={selected === undefined || busy} onClick={() => void saveAndMove()}>{current === (attempt?.questions.length ?? 1) - 1 ? "Save & submit" : "Save & next"}</PrimaryButton></div>}</footer>
          </div></div></>}
      </section>
    </div>}
  </main></AppShell>;
}

function PaperSummary({ summary, onClose }: { summary: PaperAttemptSummary; onClose: () => void }) {
  const hasScore = summary.scored_questions > 0;
  return <div className="paper-summary"><span><Check size={26} /></span><h2>Paper submitted</h2><p>{hasScore ? `Your answers were checked against ${summary.scored_questions} verified keys.` : "Your complete attempt is saved. Marks will appear when the official key is available."}</p><div><small>Completion</small><strong>{summary.answered_questions}/{summary.total_questions}</strong><small>Score</small><strong>{hasScore ? `${summary.score}/${summary.max_score}` : "Key pending"}</strong><small>Accuracy</small><strong>{summary.accuracy == null ? "—" : `${summary.accuracy}%`}</strong><small>Correct</small><strong>{hasScore ? `${summary.correct_answers}/${summary.scored_questions}` : "—"}</strong><small>Time</small><strong>{formatTime(summary.duration_seconds)}</strong></div><PrimaryButton href="/progress">Open progress</PrimaryButton><button onClick={onClose}>Return to papers</button></div>;
}
