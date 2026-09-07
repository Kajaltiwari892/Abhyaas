"use client";

import { ArrowLeft, ArrowRight, Bookmark, Calendar, Check, Clock3, ExternalLink, FileCheck2, FileText, ShieldCheck, Sparkles, X } from "lucide-react";
import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import AppShell from "../components/AppShell";
import { useAuth } from "../components/AuthProvider";
import PrimaryButton from "@/components/ui/primary-button";
import { ApiError } from "@/lib/auth-api";
import paperCrops from "@/lib/paper-crops.json";
import paperQuestionText from "@/lib/paper-question-text.json";
import { completePaperAttempt, generatePaperExplanation, getPaper, getPapers, savePaperAnswer, startPaperAttempt, type PaperAIExplanation, type PaperAttempt, type PaperAttemptSummary, type PaperDetail, type PaperListItem } from "@/lib/study-api";

type PaperMode = "review" | "mock" | "summary" | null;
type PaperCrop = { x: number; y: number; width: number; height: number; pixelWidth: number; pixelHeight: number; imageUrl?: string };
type PaperQuestionText = { prompt: string; options: string[]; ocrConfidence: number };
type PaperSection = { from: number; to: number; title: string; directions: string; passage?: string };
const PAPER_YEARS = [2026, 2025, 2024] as const;
const ENGLISH_2026_SECTIONS: PaperSection[] = [
  { from: 1, to: 10, title: "Pair of words", directions: "A pair of words is provided. Select the option that most appropriately describes the meaning of both words." },
  { from: 11, to: 20, title: "Nearest meaning", directions: "Select the option nearest in meaning to the underlined word in the given sentence." },
  { from: 21, to: 30, title: "Word meaning", directions: "Select the most appropriate meaning of the given word from the options provided." },
  { from: 31, to: 40, title: "Ordering of sentences", directions: "The first and sixth sentences are fixed as S1 and S6. Arrange the four jumbled sentences P, Q, R and S in the correct sequence." },
  { from: 41, to: 50, title: "Idioms and phrases", directions: "Select the most appropriate meaning of the given idiom or phrase." },
  { from: 51, to: 60, title: "Opposite meaning", directions: "Select the option opposite in meaning to the underlined word in the given sentence." },
  { from: 61, to: 70, title: "Word class", directions: "Identify the word class to which the underlined word belongs." },
  { from: 71, to: 80, title: "Fill in the blank", directions: "Select the most appropriate preposition or determiner for the blank space." },
  { from: 81, to: 90, title: "Usage of similar-sounding words", directions: "Review the similar-sounding words and select the sentences in which they have been used appropriately." },
  { from: 91, to: 100, title: "Relationship between sentences", directions: "Select the most appropriate relationship of the second sentence to the first." },
  { from: 101, to: 110, title: "Match the following", directions: "Match List I with List II and select the correct answer using the code given below the lists." },
  { from: 111, to: 115, title: "Spotting errors", directions: "Identify the underlined part containing an error. If there is no error, select option D." },
  {
    from: 116,
    to: 120,
    title: "Reading comprehension",
    directions: "Read the passage carefully and answer the question using only the information in the passage.",
    passage: "As the new century begins, it is becoming evident to urban dwellers, whether in industrial or developing countries, that there is an immanent conflict between the automobile and the city. Urban air pollution, often from automobiles, claims millions of lives. Congestion also takes a direct economic toll in rising costs in time and the use of petrol.\n\nAnother cost of cities that are devoted to cars is a psychological one, a deprivation of contact with the natural world—an ‘asphalt complex’. There is a growing body of evidence that there is an innate human need for contact with nature. Both ecologists and psychologists have been aware of this for some time. Ecologists, led by Harvard University biologist E. O. Wilson, have formulated the ‘biophilia hypothesis’, which argues that those who are deprived of contact with nature suffer psychologically and that this deprivation leads to a measurable decline in well-being.\n\nMeanwhile psychologists have coined their own term—ecopsychology—in which they make the same argument. Theodore Roszak, a leader in this field, cites a study that documents humans’ dependence on nature by looking at the rate of recovery of patients in a hospital in Pennsylvania. Those whose rooms overlooked gardens with grass, trees, flowers, and birds recovered from illnesses more quickly than those who were in rooms overlooking the parking lot.",
  },
];
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
  const [aiExplanations, setAiExplanations] = useState<Record<string, PaperAIExplanation>>({});
  const [aiBusy, setAiBusy] = useState("");
  const [remaining, setRemaining] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const questionPanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    getPapers({ year: year ? Number(year) : undefined, cycle: cycle || undefined, subject: subject || undefined })
      .then(data => { if (!cancelled) { setPapers(data); setError(""); } })
      .catch((reason: unknown) => { if (!cancelled) setError(messageFor(reason, "The paper archive could not be loaded.")); });
    return () => { cancelled = true; };
  }, [cycle, subject, year]);

  const closeWorkspace = useCallback(() => {
    if (busy) return;
    setMode(null); setDetail(null); setAttempt(null); setSummary(null); setCurrent(0); setAnswers({}); setMarked({}); setRevealed({}); setAiExplanations({}); setAiBusy(""); setError("");
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

  useEffect(() => {
    questionPanelRef.current?.scrollTo({ top: 0 });
  }, [current, mode]);

  useEffect(() => {
    if (error) toast.error("Something needs attention", { description: error, id: "papers-error" });
  }, [error]);

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

  const askAI = async () => {
    const paperId = attempt?.paper_id ?? detail?.id;
    if (!accessToken || !paperId || !activeQuestion || aiBusy) return;
    setAiBusy(activeQuestion.id); setError("");
    try {
      const result = await generatePaperExplanation(accessToken, paperId, activeQuestion.id);
      setAiExplanations(values => ({ ...values, [activeQuestion.id]: result }));
      toast.success("AI explanation ready", { description: `Question ${activeQuestion.number} has been analysed.`, id: "papers-ai" });
    } catch (reason) {
      toast.error("AI explanation unavailable", {
        description: messageFor(reason, "An AI explanation could not be generated."),
        id: "papers-ai-error",
      });
    }
    finally { setAiBusy(""); }
  };

  const reviewQuestion = mode === "review" ? detail?.questions[current] : undefined;
  const activeQuestion = reviewQuestion ?? attempt?.questions[current];
  const solutionQuestion = activeQuestion
    ? detail?.questions.find(question => question.id === activeQuestion.id)
    : undefined;
  const activeCrop = activeQuestion?.asset_url
    ? (paperCrops as Record<string, PaperCrop>)[`${activeQuestion.asset_url}#${activeQuestion.number}`]
    : undefined;
  const readableQuestion = activeQuestion?.asset_url
    ? (paperQuestionText as Record<string, PaperQuestionText>)[`${activeQuestion.asset_url}#${activeQuestion.number}`]
    : undefined;
  const displayOptions = readableQuestion?.options ?? activeQuestion?.options ?? [];
  const activeSection = activeQuestion && detail?.year === 2026 && detail.cycle === "I" && detail.subject_slug === "english"
    ? ENGLISH_2026_SECTIONS.find(section => activeQuestion.number >= section.from && activeQuestion.number <= section.to)
    : undefined;
  const aiExplanation = activeQuestion ? aiExplanations[activeQuestion.id] : undefined;
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
        {mode === "summary" && summary ? <PaperSummary summary={summary} onClose={closeWorkspace} /> : activeQuestion && <><div className="paper-attempt-progress" aria-label={`${answeredCount} of ${totalAttemptQuestions} questions answered`}><div><span>{mode === "mock" ? `${answeredCount} answered` : "Paper review"}</span><small>{mode === "mock" ? `${totalAttemptQuestions - answeredCount} remaining` : `${detail?.questions.length ?? 0} questions`}</small></div><i><b style={{ width: `${mode === "mock" && totalAttemptQuestions ? answeredCount * 100 / totalAttemptQuestions : 100}%` }} /></i></div><div className="paper-question-layout">
          <nav className="paper-question-navigation" aria-label="Question navigation"><label><span>Jump to question</span><select value={current} onChange={event => setCurrent(Number(event.target.value))}>{(mode === "review" ? detail?.questions : attempt?.questions)?.map((question, index) => <option key={question.id} value={index}>Question {question.number}{answers[question.id] !== undefined ? " - answered" : ""}</option>)}</select></label><div><small>Current question</small><strong>{activeQuestion.number}</strong><span>of {(mode === "review" ? detail?.questions.length : attempt?.questions.length) ?? 0}</span></div></nav>
          <div className="paper-question-panel" ref={questionPanelRef}>
            {mode === "mock" && <div className="paper-question-tools"><button className={marked[activeQuestion.id] ? "marked" : ""} onClick={() => setMarked(values => ({ ...values, [activeQuestion.id]: !values[activeQuestion.id] }))}><Bookmark size={14} /> {marked[activeQuestion.id] ? "Marked for review" : "Mark for review"}</button></div>}
            <div className="paper-question-content">
              <article className="paper-sheet">
                {activeSection && <header className="paper-directions"><span>Directions</span><h3>{activeSection.title}</h3><p>{activeSection.directions}</p></header>}
                {activeSection?.passage && <section className="paper-passage"><strong>Passage</strong>{activeSection.passage.split("\n\n").map(paragraph => <p key={paragraph}>{paragraph}</p>)}</section>}
                <section className="paper-sheet-question"><small>Question {activeQuestion.number}</small>{readableQuestion ? <h2>{readableQuestion.prompt}</h2> : activeQuestion.asset_url && activeCrop?.imageUrl ? <figure className="paper-question-scan is-cropped"><Image src={activeCrop.imageUrl} width={activeCrop.pixelWidth} height={activeCrop.pixelHeight} alt={`Official UPSC question ${activeQuestion.number}`} /><figcaption><span>Official question {activeQuestion.number}</span><a href={activeQuestion.asset_url} target="_blank" rel="noreferrer">View source page <ExternalLink size={11} /></a></figcaption></figure> : <div className="paper-crop-pending"><FileText size={18} /><div><strong>Individual question view is being prepared</strong><p>Use the official source while question {activeQuestion.number} is checked.</p></div></div>}</section>
                <section className="paper-answer-panel" aria-label={`Answer question ${activeQuestion.number}`}><header><strong>Choose an answer</strong><span>Select one option</span></header><div className="paper-mcq-options">{displayOptions.map((option, index) => { const answerIsRevealed = Boolean(revealed[activeQuestion.id]); const correct = Boolean(answerIsRevealed && solutionQuestion?.is_verified && solutionQuestion.correct_index === index); const incorrect = Boolean(answerIsRevealed && selected === index && solutionQuestion?.is_verified && solutionQuestion.correct_index !== index); return <button aria-pressed={selected === index} className={`${selected === index ? "selected" : ""} ${correct ? "correct" : ""} ${incorrect ? "incorrect" : ""}`} key={`${activeQuestion.id}-${index}`} onClick={() => { setAnswers(values => ({ ...values, [activeQuestion.id]: index })); setRevealed(values => ({ ...values, [activeQuestion.id]: false })); }}><span>{String.fromCharCode(65 + index)}</span><span className="paper-option-copy">{option}</span>{correct && <Check size={15} />}</button>; })}</div>
                {solutionQuestion?.is_verified && !revealed[activeQuestion.id] && <button className="paper-reveal-answer" onClick={() => setRevealed(values => ({ ...values, [activeQuestion.id]: true }))}>{selected === undefined ? "Reveal answer and explanation" : "Check answer and explanation"}</button>}
                {solutionQuestion?.is_verified && revealed[activeQuestion.id] && solutionQuestion.explanation && <div className="paper-explanation"><small>{selected === solutionQuestion.correct_index ? "Correct answer" : "Official answer"}</small><p>{solutionQuestion.explanation}</p><span><FileCheck2 size={13} /> {solutionQuestion.source_label}</span></div>}
                {!solutionQuestion?.is_verified && <button className="paper-ai-answer" onClick={() => void askAI()} disabled={aiBusy === activeQuestion.id}><Sparkles size={15} /> {aiBusy === activeQuestion.id ? "Working…" : aiExplanation ? "Explain again" : "Explain with AI"}</button>}
                {aiExplanation && <div className="paper-explanation is-ai"><small>AI suggests option {String.fromCharCode(65 + aiExplanation.correct_index)} · {aiExplanation.confidence} confidence</small><p>{aiExplanation.explanation}</p><span><Sparkles size={13} /> AI-generated guidance may be imperfect; verify important facts.</span></div>}
              </section>
                {readableQuestion && activeQuestion.asset_url && activeCrop?.imageUrl && <details className="paper-source-details"><summary>See the original scanned question</summary><figure className="paper-question-scan is-cropped"><Image src={activeCrop.imageUrl} width={activeCrop.pixelWidth} height={activeCrop.pixelHeight} alt={`Official UPSC question ${activeQuestion.number}`} /><figcaption><span>Official question {activeQuestion.number}</span><a href={activeQuestion.asset_url} target="_blank" rel="noreferrer">View source page <ExternalLink size={11} /></a></figcaption></figure></details>}
              </article>
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
