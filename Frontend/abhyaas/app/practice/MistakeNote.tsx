import { ArrowUpRight, BookOpen, Check, ChevronDown, ExternalLink, Lightbulb, Minus, PencilLine } from "lucide-react";
import Link from "next/link";
import type { NotebookEntry } from "@/lib/notebook-api";
import NotebookText from "./NotebookText";
import s from "./notebook.module.css";

function validChoice(index: number | null | undefined, options: string[]) {
  return typeof index === "number" && Number.isInteger(index) && index >= 0 && index < options.length;
}

export function noteExplanation(value: string) {
  const text = value.trim();
  // A key-only record confirms the option, but does not explain the concept.
  if (/^The (?:official|provisional) UPSC .*answer key marks option \([a-j]\)\.?$/i.test(text)
    || /^(?:Answer verification pending|Explanation (?:not available|pending))\.?$/i.test(text)) return "";
  return text;
}

export function noteHelp(item: NotebookEntry) {
  const question = [
    "Please explain how to solve this question step by step. Explain the rule or concept, not just the option letter.",
    item.context, item.prompt,
    item.options.map((option, i) => `${String.fromCharCode(65 + i)}. ${option}`).join("\n"),
  ].filter(Boolean).join("\n\n");
  // Respect the tutor's 1,500-character request limit without cutting a passage
  // or answer option mid-sentence. Long questions get honest topic-level help.
  const exact = question.length <= 1500;
  const prompt = exact ? question : `Help me revise ${item.topic || "this topic"} in ${item.subject}. Explain the main concepts and a worked example, in simple steps.`.slice(0, 1500);
  return { href: `/doubt-solver?${new URLSearchParams({ question: prompt, subject: item.subject_slug })}`, label: exact ? "Help me understand this" : "Help me revise this topic" };
}

export function noteCitation(source: string) {
  const paper = source.match(/\bCDS\s+(I{1,2})\s+(\d{4})\s*·\s*Q(\d+)\b/i);
  return paper ? `CDS ${paper[1].toUpperCase()} ${paper[2]} · Question ${paper[3]}` : source.trim();
}

export default function MistakeNote({ item, number }: { item: NotebookEntry; number: number }) {
  const resolved = item.state === "resolved";
  const hasSavedMistake = item.mistake_selected_index !== undefined;
  // Older APIs cannot reconstruct the earlier choice after a successful retry.
  // Never mislabel the current correct answer as the student's saved mistake.
  const choice = hasSavedMistake ? item.mistake_selected_index : resolved ? undefined : item.selected_index;
  const skipped = hasSavedMistake ? choice === null : item.reason === "skipped";
  const correctAvailable = item.review_available && validChoice(item.correct_index, item.options);
  const explanation = correctAvailable ? noteExplanation(item.explanation) : "";
  const help = noteHelp(item);
  const provisional = /provisional/i.test(item.source_label);
  const date = new Date(item.last_attempt_at);
  const titleId = `note-${encodeURIComponent(item.question_key)}`;

  return <article className={s.note} aria-labelledby={titleId}>
    <div className={s.paperBinding} aria-hidden="true">{Array.from({ length: 6 }, (_, i) => <span key={i} />)}</div>
    <header className={s.noteHeader}>
      <span className={s.noteNumber}>{String(number).padStart(2, "0")}</span>
      <div className={s.noteTitle}><small>{item.subject}</small><h2 id={titleId}>{item.topic || "Revision note"}</h2></div>
      <span className={`${s.noteStatus} ${resolved ? s.noteResolved : ""}`}>{resolved ? <Check size={13} /> : skipped ? <Minus size={13} /> : <PencilLine size={13} />}{resolved ? "Revised" : skipped ? "Left unanswered" : "To revisit"}</span>
    </header>
    <p className={s.noteQuestion}><NotebookText text={item.prompt} /></p>
    <div className={s.answerComparison}>
      <section className={s.previousAnswer} aria-label={resolved ? "Your earlier answer" : "Your answer"}>
        <h3>{resolved ? "Your earlier answer" : "Your answer"}</h3>
        {skipped ? <p className={s.answerFallback}>You left this one unanswered. Let’s work through it.</p>
          : validChoice(choice, item.options) ? <p><span className={s.choiceLetter}>{String.fromCharCode(65 + choice!)}.</span><NotebookText text={item.options[choice!]} /></p>
          : <p className={s.answerFallback}>Your earlier choice isn’t available here.</p>}
      </section>
      <section className={s.correctAnswer} aria-label="Correct answer">
        <h3><Check size={13} /> Correct answer</h3>
        {correctAvailable ? <p><span className={s.choiceLetter}>{String.fromCharCode(65 + item.correct_index)}.</span><NotebookText text={item.options[item.correct_index]} /></p>
          : <p className={s.answerFallback}>We can’t confirm the answer here yet. Open the original question below to review it.</p>}
        {correctAvailable && provisional && <small className={s.provisionalAnswer}>This answer is provisional and may change.</small>}
      </section>
    </div>
    {explanation ? <section className={s.correction} aria-label="Understand the correction">
      <h3><BookOpen size={15} /> {skipped ? "Let’s understand it" : "Understand the correction"}</h3>
      <p><NotebookText text={explanation} /></p>
    </section> : <Link className={s.noteHelp} href={help.href}>{help.label} <ArrowUpRight size={14} /></Link>}
    {explanation && <div className={s.nextTime}><Lightbulb size={16} /><div><h3>Next time</h3><p>Try again without looking at the answer. Compare your reasoning with the explanation, not just the option letter.</p></div></div>}
    <details className={s.questionDetails}>
      <summary>{item.context ? "Read passage & all options" : "View all options"}<ChevronDown size={15} /></summary>
      {item.context && <div className={s.context}><NotebookText text={item.context} /></div>}
      <ol className={s.noteOptions} type="A">{item.options.map((option, i) => <li key={i}><NotebookText text={option} /></li>)}</ol>
    </details>
    <footer className={s.noteFooter}>
      <div className={s.noteMeta}><span className={s.noteSource} title={item.source_label}>{noteCitation(item.source_label)}</span>{Number.isFinite(date.getTime()) && <time dateTime={item.last_attempt_at}>Practised on {date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" })}</time>}</div>
      {(item.source_page_url || item.source_url) && <div className={s.noteLinks}>{item.source_page_url && <a href={item.source_page_url} target="_blank" rel="noreferrer">Original question <ExternalLink size={12} /></a>}{item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">Original paper <ExternalLink size={12} /></a>}</div>}
    </footer>
  </article>;
}
