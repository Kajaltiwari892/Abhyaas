"use client";

import { ArrowLeft, ArrowRight, Bookmark, Calendar, Check, Clock3, ExternalLink, FileCheck2, FileText, ShieldCheck, Sparkles, Square, Volume2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import AppShell from "../components/AppShell";
import { useAuth } from "../components/AuthProvider";
import PaperArchiveSkeleton from "../components/PaperArchiveSkeleton";
import PaperQuestionSkeleton from "../components/PaperQuestionSkeleton";
import PaperText from "../components/PaperText";
import PrimaryButton from "@/components/ui/primary-button";
import { ApiError } from "@/lib/auth-api";
import { filterPaperArchive, paperArchiveYears, paperAvailability } from "@/lib/paper-archive";
import { completePaperAttempt, generatePaperExplanation, getPaper, getPaperAttemptResult, getPapers, savePaperAnswer, startPaperAttempt, type PaperAIExplanation, type PaperAttempt, type PaperAttemptSummary, type PaperDetail, type PaperListItem } from "@/lib/study-api";

type PaperMode = "review" | "mock" | "summary" | null;
type PaperSection = { from: number; to: number; title: string; directions: string; passage?: string };
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
const LATEX_WORDS: Record<string, string> = {
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", lambda: "λ", pi: "π", theta: "θ",
  times: "×", cdot: "·", dots: "…", circ: "°", neq: "≠", ne: "≠", le: "≤", ge: "≥",
  pm: "±", angle: "∠", tan: "tan", cot: "cot", sin: "sin", cos: "cos", sec: "sec",
  csc: "cosec", quad: " ", displaystyle: "", left: "", right: "",
};
const SUPERSCRIPT_DIGITS: Record<string, string> = { "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻" };

function bracedGroup(text: string, opening: number) {
  if (text[opening] !== "{") return null;
  let depth = 0;
  for (let index = opening; index < text.length; index += 1) {
    if (text[index] === "{") depth += 1;
    if (text[index] === "}") depth -= 1;
    if (depth === 0) return { value: text.slice(opening + 1, index), end: index + 1 };
  }
  return null;
}

function replaceLatexGroups(text: string, command: "frac" | "sqrt") {
  const marker = `\\${command}{`;
  let result = text;
  let start = result.indexOf(marker);
  while (start >= 0) {
    const first = bracedGroup(result, start + marker.length - 1);
    if (!first) break;
    if (command === "sqrt") {
      result = `${result.slice(0, start)}√(${first.value})${result.slice(first.end)}`;
    } else {
      const second = bracedGroup(result, first.end);
      if (!second) break;
      result = `${result.slice(0, start)}(${first.value})/(${second.value})${result.slice(second.end)}`;
    }
    start = result.indexOf(marker, start + 1);
  }
  return result;
}

function formatPaperText(value: string) {
  let text = value.replace(/\$/g, "");
  for (let pass = 0; pass < 4; pass += 1) {
    text = replaceLatexGroups(replaceLatexGroups(text, "frac"), "sqrt");
  }
  text = text
    .replace(/\\text\{([^{}]*)\}/g, "$1")
    .replace(/\^\{(-?\d+)\}/g, (_, digits: string) => [...digits].map(digit => SUPERSCRIPT_DIGITS[digit] ?? digit).join(""))
    .replace(/\^\{([^{}]+)\}/g, "^($1)")
    .replace(/_\{([^{}]+)\}/g, "_($1)")
    .replace(/\\([A-Za-z]+)/g, (_, word: string) => LATEX_WORDS[word] ?? word)
    .replace(/\\([()[\]])/g, "$1")
    .replace(/\\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .trim();
  return text;
}
const formatTime = (seconds: number) => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
const messageFor = (reason: unknown, fallback: string) => reason instanceof ApiError ? reason.message : fallback;

export default function PapersPage() {
  const { accessToken } = useAuth();
  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [listingLoading, setListingLoading] = useState(true);
  const [year, setYear] = useState("");
  const [cycle, setCycle] = useState("");
  const [subject, setSubject] = useState("");
  const [mode, setMode] = useState<PaperMode>(null);
  const [openingPaper, setOpeningPaper] = useState<{ paper: PaperListItem; mode: "mock" | "review" } | null>(null);
  const openingRequest = useRef<AbortController | null>(null);
  const [detail, setDetail] = useState<PaperDetail | null>(null);
  const [attempt, setAttempt] = useState<PaperAttempt | null>(null);
  const [summary, setSummary] = useState<PaperAttemptSummary | null>(null);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [answerBusy, setAnswerBusy] = useState("");
  const [marked, setMarked] = useState<Record<string, boolean>>({});
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const [aiExplanations, setAiExplanations] = useState<Record<string, PaperAIExplanation>>({});
  const [aiBusy, setAiBusy] = useState("");
  const [speakingQuestion, setSpeakingQuestion] = useState("");
  const [remaining, setRemaining] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const questionPanelRef = useRef<HTMLDivElement>(null);
  const closePaperRef = useRef<HTMLButtonElement>(null);
  const workspaceOpen = Boolean(mode || openingPaper);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) setListingLoading(true); });
    getPapers()
      .then(data => { if (!cancelled) { setPapers(data); setError(""); } })
      .catch((reason: unknown) => { if (!cancelled) setError(messageFor(reason, "The paper archive could not be loaded.")); })
      .finally(() => { if (!cancelled) setListingLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const closeWorkspace = useCallback(() => {
    if (busy && !openingRequest.current) return;
    const pending = openingRequest.current;
    openingRequest.current = null;
    pending?.abort();
    setOpeningPaper(null); setBusy(false);
    window.speechSynthesis?.cancel();
    setMode(null); setDetail(null); setAttempt(null); setSummary(null); setCurrent(0); setAnswers({}); setAnswerBusy(""); setMarked({}); setRevealed({}); setAiExplanations({}); setAiBusy(""); setSpeakingQuestion(""); setError("");
  }, [busy]);

  useEffect(() => {
    if (!workspaceOpen) return;
    const handleKey = (event: KeyboardEvent) => { if (event.key === "Escape") closeWorkspace(); };
    document.body.classList.add("paper-dialog-open");
    window.addEventListener("keydown", handleKey);
    return () => { document.body.classList.remove("paper-dialog-open"); window.removeEventListener("keydown", handleKey); };
  }, [closeWorkspace, workspaceOpen]);

  useEffect(() => {
    if (!workspaceOpen) return;
    const trigger = document.activeElement;
    closePaperRef.current?.focus();
    return () => { if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus(); };
  }, [workspaceOpen]);

  useEffect(() => () => {
    const pending = openingRequest.current;
    openingRequest.current = null;
    pending?.abort();
  }, []);

  useEffect(() => {
    if (mode !== "mock" || !attempt || remaining <= 0) return;
    const timer = window.setInterval(() => setRemaining(value => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [attempt, mode, remaining]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      if (questionPanelRef.current) questionPanelRef.current.scrollTop = 0;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [current, mode]);

  useEffect(() => {
    if (error) toast.error("Something needs attention", { description: error, id: "papers-error" });
  }, [error]);

  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  const openPaper = async (paper: PaperListItem, requestedMode: "mock" | "review") => {
    // The ref guards rapid double-clicks before React has rendered disabled buttons.
    if (!accessToken || busy || openingRequest.current) return;
    const request = new AbortController();
    openingRequest.current = request;
    setOpeningPaper({ paper, mode: requestedMode });
    setBusy(true); setError("");
    const timeout = window.setTimeout(() => request.abort(), 30_000);
    try {
      const [next, paperDetail] = await Promise.all([
        requestedMode === "mock" ? startPaperAttempt(accessToken, paper.id, request.signal) : Promise.resolve(null),
        getPaper(accessToken, paper.id, request.signal),
      ]);
      // Closing, navigating away or opening another paper invalidates this response.
      if (openingRequest.current !== request) return;
      if (!(next?.questions ?? paperDetail.questions).length) {
        throw new ApiError("No interactive questions are available for this paper. Please open its official PDF.", 409);
      }
      setDetail(paperDetail); setRevealed({}); setSummary(null);
      if (next) {
        const restoredAnswers = Object.fromEntries(next.answers.map(answer => [answer.question_id, answer.selected_index]));
        const restoredMarked = Object.fromEntries(next.answers.map(answer => [answer.question_id, answer.marked_for_review]));
        const firstUnanswered = next.questions.findIndex(question => restoredAnswers[question.id] === undefined);
        setAttempt(next); setRemaining(Math.max(0, next.duration_seconds - next.elapsed_seconds)); setAnswers(restoredAnswers); setAnswerBusy(""); setMarked(restoredMarked); setCurrent(firstUnanswered >= 0 ? firstUnanswered : Math.max(0, next.questions.length - 1));
        if (next.resumed) toast.success("Paper resumed", { description: `${next.answers.length} saved ${next.answers.length === 1 ? "answer" : "answers"} restored.` });
      } else {
        setAttempt(null); setCurrent(0); setAnswers({});
      }
      setMode(requestedMode);
    } catch (reason) {
      if (openingRequest.current === request) {
        setError(request.signal.aborted ? "Opening this paper took too long. Please try again." : messageFor(reason, "The paper could not be opened. Please try again."));
      }
    } finally {
      window.clearTimeout(timeout);
      request.abort();
      if (openingRequest.current === request) {
        openingRequest.current = null;
        setOpeningPaper(null); setBusy(false);
      }
    }
  };

  const submitMock = useCallback(async () => {
    if (!accessToken || !attempt || busy) return;
    setBusy(true); setError("");
    try {
      const elapsed = Math.max(0, attempt.duration_seconds - remaining);
      const finalAnswers = Object.entries(answers).map(([questionId, selectedIndex]) => ({
        question_id: questionId,
        selected_index: selectedIndex,
        marked_for_review: Boolean(marked[questionId]),
      }));
      const result = await completePaperAttempt(accessToken, attempt.id, elapsed, finalAnswers);
      setSummary(result);
      setMode("summary");
      toast.success("Paper saved to your history", { description: "Your score and attempt details are now available in Progress." });
    } catch (reason) {
      try {
        const recoveredResult = await getPaperAttemptResult(accessToken, attempt.id);
        setSummary(recoveredResult);
        setMode("summary");
        toast.success("Result recovered", { description: "The paper was submitted successfully and your score is ready." });
      } catch {
        setError(messageFor(reason, "The paper could not be submitted."));
      }
    }
    finally { setBusy(false); }
  }, [accessToken, answers, attempt, busy, marked, remaining]);

  const speakExplanation = (text: string, questionId: string) => {
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
      toast.error("Voice playback is unavailable", { description: "This browser does not support text-to-speech." });
      return;
    }
    window.speechSynthesis.cancel();
    if (speakingQuestion === questionId) { setSpeakingQuestion(""); return; }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.95;
    utterance.pitch = 1;
    utterance.onend = () => setSpeakingQuestion("");
    utterance.onerror = () => { setSpeakingQuestion(""); toast.error("Voice playback stopped", { description: "Please try listening again." }); };
    setSpeakingQuestion(questionId);
    window.speechSynthesis.speak(utterance);
  };

  const selectPaperAnswer = async (selectedIndex: number) => {
    if (!activeQuestion) return;
    setAnswers(values => ({ ...values, [activeQuestion.id]: selectedIndex }));
    setRevealed(values => ({ ...values, [activeQuestion.id]: false }));
    if (mode !== "mock" || !accessToken || !attempt || answerBusy) return;
    const questionId = activeQuestion.id;
    const questionIndex = current;
    setAnswerBusy(questionId); setError("");
    try {
      const elapsed = Math.max(0, attempt.duration_seconds - remaining);
      await savePaperAnswer(accessToken, attempt.id, questionId, { selected_index: selectedIndex, marked_for_review: Boolean(marked[questionId]), elapsed_seconds: elapsed });
      window.setTimeout(() => {
        setCurrent(index => index === questionIndex && index < attempt.questions.length - 1 ? index + 1 : index);
      }, 450);
    } catch (reason) {
      setAnswers(values => { const next = { ...values }; delete next[questionId]; return next; });
      setError(messageFor(reason, "Your answer could not be saved."));
    } finally { setAnswerBusy(""); }
  };

  const toggleQuestionMark = async () => {
    if (!activeQuestion) return;
    const questionId = activeQuestion.id;
    const nextMarked = !marked[questionId];
    setMarked(values => ({ ...values, [questionId]: nextMarked }));
    const selectedIndex = answers[questionId];
    if (mode !== "mock" || !accessToken || !attempt || selectedIndex === undefined || answerBusy) return;
    try {
      const elapsed = Math.max(0, attempt.duration_seconds - remaining);
      await savePaperAnswer(accessToken, attempt.id, questionId, { selected_index: selectedIndex, marked_for_review: nextMarked, elapsed_seconds: elapsed });
    } catch (reason) {
      setMarked(values => ({ ...values, [questionId]: !nextMarked }));
      setError(messageFor(reason, "The review marker could not be saved."));
    }
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
  const readableQuestion = activeQuestion?.transcription;
  const displayOptions = readableQuestion?.options ?? activeQuestion?.options ?? [];
  const sourcePageUrl = readableQuestion?.sourcePageUrl ?? activeQuestion?.asset_url;
  const transcribedSection = readableQuestion && (readableQuestion.sectionTitle || readableQuestion.directions || readableQuestion.passage)
    ? {
        title: readableQuestion.sectionTitle ?? "Instructions",
        directions: readableQuestion.directions ?? "",
        passage: readableQuestion.passage,
      }
    : undefined;
  const activeSection = transcribedSection ?? (
    activeQuestion && detail?.year === 2026 && detail.cycle === "I" && detail.subject_slug === "english"
      ? ENGLISH_2026_SECTIONS.find(section => activeQuestion.number >= section.from && activeQuestion.number <= section.to)
      : undefined
  );
  const aiExplanation = activeQuestion ? aiExplanations[activeQuestion.id] : undefined;
  const selected = activeQuestion ? answers[activeQuestion.id] : undefined;
  const answerStatus = mode === "mock"
    ? answerBusy === activeQuestion?.id
      ? "Saving answer…"
      : selected !== undefined
        ? "Answer saved — you can change it before submitting"
        : "Select one option"
    : "Select an option, then reveal the answer when you are ready";
  const answeredCount = Object.keys(answers).length;
  const totalAttemptQuestions = attempt?.questions.length ?? 0;
  const visibleQuestionCount = (mode === "review" ? detail?.questions.length : attempt?.questions.length) ?? 0;
  const progressPercent = mode === "mock" && totalAttemptQuestions
    ? Math.round(answeredCount * 1000 / totalAttemptQuestions) / 10
    : 0;
  const marksPerQuestion = detail ? detail.total_marks / detail.official_question_count : 0;
  const penaltyPerWrongAnswer = detail ? marksPerQuestion * detail.negative_mark_fraction : 0;
  const archiveYears = paperArchiveYears(papers);
  const filteredPapers = filterPaperArchive(papers, { year, cycle, subject });
  const papersByYear = archiveYears
    .map((paperYear) => ({ year: paperYear, papers: filteredPapers.filter((paper) => paper.year === paperYear) }))
    .filter((group) => group.papers.length > 0);

  return <AppShell active="Previous papers"><main className="workspace papers-workspace">
    <header className="workspace-header"><div><span className="workspace-kicker">Learn from the real examination</span><h1>Previous papers</h1><p>Browse official CDS papers by year, cycle and subject. Open the full PDF or practise papers marked interactive.</p></div><div className="workspace-badge"><FileCheck2 size={15} /> Official archive</div></header>
    <section className="paper-filters">
      <label><Calendar size={15} /><select aria-label="Filter by year" value={year} onChange={event => setYear(event.target.value)}><option value="">All years</option>{archiveYears.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      <label><ShieldCheck size={15} /><select aria-label="Filter by cycle" value={cycle} onChange={event => setCycle(event.target.value)}><option value="">Both cycles</option><option value="I">CDS I</option><option value="II">CDS II</option></select></label>
      <label><FileText size={15} /><select aria-label="Filter by subject" value={subject} onChange={event => setSubject(event.target.value)}><option value="">All subjects</option><option value="english">English</option><option value="general-knowledge">General Knowledge</option><option value="elementary-mathematics">Elementary Mathematics</option></select></label>
      <span aria-live="polite">{listingLoading ? "Loading papers…" : `${filteredPapers.length} of ${papers.length} official papers`}</span>
    </section>
    <div className="papers-by-year">{papersByYear.map((group) => <section className="paper-year-group" key={group.year}>
      <header className="paper-year-heading"><div><span>{group.year}</span><div><h2>{group.year} question papers</h2><p>English, General Knowledge and Elementary Mathematics.</p></div></div><strong>{group.papers.length} {group.papers.length === 1 ? "paper" : "papers"}</strong></header>
      <div className="paper-type-grid">{group.papers.map((paper) => <article key={paper.id}>
        <header className="paper-card-top"><span className="paper-year-badge">{paper.year}</span><span className="paper-cycle-badge">CDS {paper.cycle}</span><FileText size={21} /></header>
        <div className="paper-card-copy"><small>{paper.academy_tracks.join(" / ")}</small><h2>{paper.subject_name}</h2><p>{paperAvailability(paper) === "pdf" ? "Complete original UPSC PDF. Interactive questions have not been prepared for this paper yet." : paperAvailability(paper) === "interactive" ? "Interactive paper · every question available to practise." : `${paper.available_question_count} interactive questions available. Use the PDF for the complete paper.`}</p></div>
        <div className="paper-card-meta"><span><strong>{paper.official_question_count}</strong><small>Paper questions</small></span><span><strong>{paper.duration_seconds / 3600} hr</strong><small>Duration</small></span><span><strong>{paper.total_marks}</strong><small>Marks</small></span></div>
        <p className="paper-key-status"><ShieldCheck size={14} /> {paperAvailability(paper) === "pdf" ? "Official PDF · online scoring not available" : paper.verified_question_count ? `${paper.verified_question_count} verified answers available` : "Answer verification pending"}</p>
        <div className="paper-actions">{paper.available_question_count > 0 ? <><PrimaryButton size="sm" onClick={() => void openPaper(paper, "mock")} disabled={busy}><Clock3 size={15} /> Solve paper</PrimaryButton><button disabled={busy || !paper.solutions_available} onClick={() => void openPaper(paper, "review")}>Review <ArrowRight size={15} /></button></> : <a className="primary-button primary-button--sm" href={paper.source_url} target="_blank" rel="noreferrer"><FileText size={15} /> Open official PDF <ExternalLink size={13} /></a>}</div>
        {paper.available_question_count > 0 && <a className="paper-source-link" href={paper.source_url} target="_blank" rel="noreferrer">View UPSC source <ExternalLink size={12} /></a>}
      </article>)}</div>
    </section>)}</div>
    {!papers.length && listingLoading && <PaperArchiveSkeleton />}
    {!filteredPapers.length && !listingLoading && !error && <section className="paper-empty"><FileText size={25} /><h2>{year ? `No ${year} paper matches these filters.` : "No paper matches these filters."}</h2><p>This combination is not in the available official archive. Try another year, cycle, or subject.</p><button onClick={() => { setYear(""); setCycle(""); setSubject(""); }}>Clear filters</button></section>}
    <section className="paper-method"><div><span className="workspace-kicker">Archive coverage</span><h2>Original papers. Clear availability.</h2></div><div><article><strong>01 · Official PDFs</strong><p>Coverage follows UPSC’s currently available online listings, not every historical CDS sitting. The older archive begins with CDS II 2016. <a href="https://www.upsc.gov.in/examinations/previous-question-papers/archives" target="_blank" rel="noreferrer">Check the UPSC archive.</a></p></article><article><strong>02 · Interactive practice</strong><p>PDF-only papers are not presented as ready-to-score mocks. Interactive papers retain your saved attempts; marks use verified answers only.</p></article></div></section>
    {workspaceOpen && <div className="paper-dialog-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) closeWorkspace(); }}>
      <section className="paper-dialog" role="dialog" aria-label={(openingPaper?.mode ?? mode) === "review" ? "Official paper review" : "Timed paper"}>
        <header className="paper-dialog-header"><div><small>{openingPaper ? "Opening paper" : mode === "review" ? "Review mode" : mode === "summary" ? "Attempt complete" : "Timed mock"}</small><h2>{openingPaper?.paper.title ?? detail?.title ?? attempt?.title}</h2></div>{mode === "mock" && !openingPaper && <strong><Clock3 size={15} /> {formatTime(remaining)}</strong>}<button ref={closePaperRef} aria-label="Close paper" onClick={closeWorkspace} disabled={busy && !openingPaper}><X size={19} /></button></header>
        {openingPaper ? <PaperQuestionSkeleton subject={openingPaper.paper.subject_name} /> : mode === "summary" && summary ? <PaperSummary summary={summary} questions={attempt?.questions ?? []} onClose={closeWorkspace} marksPerQuestion={marksPerQuestion} negativeMarkFraction={detail?.negative_mark_fraction ?? 0} /> : activeQuestion && <><div className="paper-attempt-progress" aria-label={`${answeredCount} of ${totalAttemptQuestions} questions answered`}><div><span>{mode === "mock" ? `${answeredCount} of ${totalAttemptQuestions} answered` : `${visibleQuestionCount} questions`}</span><small>{mode === "mock" ? `${progressPercent}% complete` : "Review mode"}</small></div><div className="paper-progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={totalAttemptQuestions} aria-valuenow={answeredCount}><span style={{ width: `${progressPercent}%` }} /></div>{mode === "mock" && <span className="paper-inline-marking" title={`Correct: +${marksPerQuestion.toFixed(2)} · Wrong: −${penaltyPerWrongAnswer.toFixed(2)} · Unattempted: 0`}><ShieldCheck size={14} /> −{penaltyPerWrongAnswer.toFixed(2)} per wrong</span>}</div><div className="paper-question-layout">
          <div className="paper-question-panel">
            <div className="paper-question-toolbar">
              <nav className="paper-question-navigation" aria-label="Question navigation"><label><span>Go to</span><select value={current} onChange={event => setCurrent(Number(event.target.value))}>{(mode === "review" ? detail?.questions : attempt?.questions)?.map((question, index) => <option key={question.id} value={index}>Question {question.number}{answers[question.id] !== undefined ? " - answered" : ""}</option>)}</select></label><div><span>Question</span><strong>{activeQuestion.number}</strong><span>of {visibleQuestionCount}</span></div></nav>
              {mode === "mock" && <div className="paper-question-tools"><button className={marked[activeQuestion.id] ? "marked" : ""} onClick={() => void toggleQuestionMark()}><Bookmark size={14} /> {marked[activeQuestion.id] ? "Marked" : "Mark for review"}</button></div>}
            </div>
            <div className="paper-question-content" ref={questionPanelRef}>
              <article className={`paper-sheet ${mode === "mock" ? "is-mock" : "is-review"}`}>
                {activeSection && <details className="paper-directions" key={`${activeQuestion.id}-directions`} open><summary><span>Directions</span><strong>{formatPaperText(activeSection.title)}</strong><small>Read instructions</small></summary>{activeSection.directions && <p><PaperText value={formatPaperText(activeSection.directions)} /></p>}</details>}
                {activeSection?.passage && <section className="paper-passage"><strong>Passage</strong>{activeSection.passage.split("\n\n").map((paragraph, index) => <p key={index}><PaperText value={formatPaperText(paragraph)} /></p>)}</section>}
                <section className="paper-sheet-question"><small>Question {activeQuestion.number}</small>{readableQuestion ? <><h2><PaperText value={formatPaperText(readableQuestion.prompt)} /></h2>{readableQuestion.hasVisual && activeQuestion.asset_url && <figure className="paper-original-figure"><a href={activeQuestion.asset_url} target="_blank" rel="noreferrer">{/* eslint-disable-next-line @next/next/no-img-element */}<img src={activeQuestion.asset_url} alt={`Original page containing the figure for question ${activeQuestion.number}`} loading="lazy" /></a><figcaption>Original figure on the complete page. Open to zoom.</figcaption></figure>}</> : <div className="paper-crop-pending"><FileText size={18} /><div><strong>Written question is being verified</strong><p>Open the complete official page to read question {activeQuestion.number} without a clipped crop.</p>{activeQuestion.asset_url && <a href={activeQuestion.asset_url} target="_blank" rel="noreferrer">Open full official page <ExternalLink size={11} /></a>}</div></div>}</section>
                <section className="paper-answer-panel" aria-label={`Answer question ${activeQuestion.number}`}><header><strong>Choose an answer</strong><span>{answerStatus}</span></header><div className="paper-mcq-options">{displayOptions.map((option, index) => { const answerIsRevealed = Boolean(revealed[activeQuestion.id]); const correct = mode !== "mock" && Boolean(answerIsRevealed && solutionQuestion?.is_verified && solutionQuestion.correct_index === index); const incorrect = mode !== "mock" && Boolean(answerIsRevealed && solutionQuestion?.is_verified && selected === index && selected !== solutionQuestion.correct_index); return <button disabled={answerBusy === activeQuestion.id} aria-pressed={selected === index} className={`${selected === index ? "selected" : ""} ${correct ? "correct" : ""} ${incorrect ? "incorrect" : ""}`} key={`${activeQuestion.id}-${index}`} onClick={() => void selectPaperAnswer(index)}><span>{String.fromCharCode(65 + index)}</span><span className="paper-option-copy">{formatPaperText(option)}</span>{correct && <Check size={15} />}{incorrect && <X size={15} />}</button>; })}</div>
                {mode === "review" && solutionQuestion?.is_verified && !revealed[activeQuestion.id] && <button className="paper-reveal-answer" onClick={() => setRevealed(values => ({ ...values, [activeQuestion.id]: true }))}>{selected === undefined ? "Reveal answer and explanation" : "Check answer and explanation"}</button>}
                {solutionQuestion?.is_verified && revealed[activeQuestion.id] && solutionQuestion.explanation && <div className="paper-explanation"><small>{selected === solutionQuestion.correct_index ? "Correct answer" : "Official answer"}</small><p>{solutionQuestion.explanation}</p><div className="paper-explanation-footer"><span><FileCheck2 size={13} /> {solutionQuestion.source_label}</span><button type="button" onClick={() => speakExplanation(solutionQuestion.explanation ?? "", activeQuestion.id)}>{speakingQuestion === activeQuestion.id ? <Square size={13} /> : <Volume2 size={14} />} {speakingQuestion === activeQuestion.id ? "Stop voice" : "Listen"}</button></div></div>}
                {mode === "review" && !solutionQuestion?.is_verified && <button className="paper-ai-answer" onClick={() => void askAI()} disabled={aiBusy === activeQuestion.id}><Sparkles size={15} /> {aiBusy === activeQuestion.id ? "Working…" : aiExplanation ? "Explain again" : "Explain with AI"}</button>}
                {aiExplanation && <div className="paper-explanation is-ai"><small>AI suggests option {String.fromCharCode(65 + aiExplanation.correct_index)} · {aiExplanation.confidence} confidence</small><p>{aiExplanation.explanation}</p><div className="paper-explanation-footer"><span><Sparkles size={13} /> AI-generated guidance may be imperfect; verify important facts.</span><button type="button" onClick={() => speakExplanation(aiExplanation.explanation, activeQuestion.id)}>{speakingQuestion === activeQuestion.id ? <Square size={13} /> : <Volume2 size={14} />} {speakingQuestion === activeQuestion.id ? "Stop voice" : "Listen"}</button></div></div>}
              </section>
                {readableQuestion && sourcePageUrl && <a className="paper-source-details" href={sourcePageUrl} target="_blank" rel="noreferrer">{readableQuestion.text_reviewed === false ? "Transcribed · text review pending. Compare with original" : "Compare with the complete official page"} <ExternalLink size={12} /></a>}
              </article>
            </div>
            <footer><button disabled={current === 0 || busy} onClick={() => setCurrent(index => index - 1)}><ArrowLeft size={15} /> Previous</button><span>{current + 1} / {(mode === "review" ? detail?.questions.length : attempt?.questions.length) ?? 0}</span>{mode === "review" ? <button disabled={current === (detail?.questions.length ?? 1) - 1} onClick={() => setCurrent(index => index + 1)}>Next <ArrowRight size={15} /></button> : <div><button className="paper-finish-paper" onClick={() => void submitMock()} disabled={busy || answeredCount === 0}>{busy ? "Calculating result…" : "Submit paper"}</button><PrimaryButton size="sm" disabled={busy || current === (attempt?.questions.length ?? 1) - 1} onClick={() => setCurrent(index => index + 1)}>Next question <ArrowRight size={14} /></PrimaryButton></div>}</footer>
          </div></div></>}
      </section>
    </div>}
  </main></AppShell>;
}

function PaperSummary({ summary, questions, onClose, marksPerQuestion, negativeMarkFraction }: { summary: PaperAttemptSummary; questions: PaperAttempt["questions"]; onClose: () => void; marksPerQuestion: number; negativeMarkFraction: number }) {
  const hasScore = summary.scored_questions > 0;
  const negativeMarks = summary.incorrect_answers * marksPerQuestion * negativeMarkFraction;
  const questionNumbers = new Map(questions.map(question => [question.id, question.number]));
  const review = summary.review
    .map(item => ({ ...item, number: questionNumbers.get(item.question_id) ?? 0 }))
    .sort((left, right) => left.number - right.number);
  const incorrectNumbers = review
    .filter(item => item.selected_index !== null && item.is_correct === false)
    .map(item => item.number);
  return <div className="paper-summary">
    <header className="paper-summary-hero"><span><Check size={24} /></span><div><small>Attempt complete</small><h2>Paper submitted</h2><p>{hasScore ? `Your result uses ${summary.scored_questions} verified answer keys. Questions awaiting an official key are not included in marks.` : "Your attempt is saved. Marks will appear after answer keys are verified."}</p></div></header>
    <section className="paper-summary-metrics" aria-label="Attempt result">
      <article><small>Score</small><strong>{hasScore ? `${summary.score}/${summary.max_score}` : "Pending"}</strong></article>
      <article><small>Correct</small><strong>{hasScore ? summary.correct_answers : "—"}</strong></article>
      <article><small>Incorrect</small><strong>{hasScore ? summary.incorrect_answers : "—"}</strong></article>
      <article><small>Unanswered</small><strong>{summary.unanswered_questions}</strong></article>
      <article><small>Negative marks</small><strong>{hasScore ? `−${negativeMarks.toFixed(2)}` : "—"}</strong></article>
      <article><small>Accuracy</small><strong>{summary.accuracy == null ? "—" : `${summary.accuracy}%`}</strong></article>
      <article><small>Completed</small><strong>{summary.answered_questions}/{summary.total_questions}</strong></article>
      <article><small>Time</small><strong>{formatTime(summary.duration_seconds)}</strong></article>
    </section>
    <section className="paper-cutoff-note"><ShieldCheck size={18} /><div><strong>Cut-off comparison</strong><p>UPSC CDS cut-offs apply to the combined academy examination, not to one subject paper. An official combined cut-off is therefore not shown against this individual-paper score.</p></div></section>
    <section className="paper-result-review">
      <header><div><small>Question review</small><h3>{incorrectNumbers.length ? `Incorrect: ${incorrectNumbers.map(number => `Q${number}`).join(", ")}` : hasScore ? "No incorrect verified answers" : "Answer verification pending"}</h3></div><div className="paper-result-legend"><span className="is-correct">Correct</span><span className="is-incorrect">Incorrect</span><span className="is-unanswered">Unanswered</span><span className="is-pending">Key pending</span></div></header>
      <div className="paper-result-grid">{review.map(item => {
        const status = item.selected_index === null ? "unanswered" : item.is_correct === null ? "pending" : item.is_correct ? "correct" : "incorrect";
        const selectedLabel = item.selected_index === null ? "not answered" : `selected ${String.fromCharCode(65 + item.selected_index)}`;
        const correctLabel = item.correct_index === null ? "answer key pending" : `correct answer ${String.fromCharCode(65 + item.correct_index)}`;
        return <span className={`is-${status}`} title={`Question ${item.number}: ${selectedLabel}; ${correctLabel}`} key={item.question_id}>Q{item.number}</span>;
      })}</div>
    </section>
    <footer><PrimaryButton href="/progress">Open progress</PrimaryButton><button onClick={onClose}>Return to papers</button></footer>
  </div>;
}
