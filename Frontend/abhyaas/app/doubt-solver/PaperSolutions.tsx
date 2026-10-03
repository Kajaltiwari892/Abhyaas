"use client";

import { ArrowRight, ExternalLink } from "lucide-react";
import type { PaperSolutionResult } from "@/lib/study-api";
import { solutionContinuation, solutionLabel } from "@/lib/paper-solution";
import PaperText from "../components/PaperText";
import s from "./doubt-solver.module.css";

export default function PaperSolutions({ result, disabled, current, onContinue }: {
  result: PaperSolutionResult; disabled: boolean; current: boolean; onContinue: () => void;
}) {
  return <section className={s.pyqResults} aria-label="Paper solutions">
    {result.paper && <div className={s.solutionToolbar}>
      <span>{result.questions.length ? `Q${result.start}–${result.end} · ${result.paper.total} in paper` : result.paper.title}</span>
      <a href={result.paper.source_url} target="_blank" rel="noreferrer">Original UPSC paper <ExternalLink size={12} /></a>
    </div>}
    {result.questions.map((question) => <article className={s.pyqCard} key={question.id}>
      <header><strong>Question {question.number}</strong><span>{question.text_reviewed ? "Source text reviewed" : "Text review pending"}</span></header>
      {question.passage && <details className={s.pyqPassage}><summary>Read the full passage</summary><p><PaperText value={question.passage} /></p></details>}
      {question.additional_context && question.additional_context !== question.passage && question.additional_context !== question.directions && <details className={s.pyqPassage}><summary>Read question context</summary><p><PaperText value={question.additional_context} /></p></details>}
      {question.directions && <p className={s.pyqDirections}><PaperText value={question.directions} /></p>}
      <p className={s.pyqPrompt}><PaperText value={question.prompt} /></p>
      {question.options.length > 0 && <ol className={s.pyqOptions} type="A">{question.options.map((option, index) => <li key={index}><PaperText value={option} /></li>)}</ol>}
      <div className={s.solutionAnswer}>
        <span className={s.solutionLabel}>{solutionLabel(question.solution.status)}</span>
        {question.solution.answer_index !== null && <strong>Answer: {String.fromCharCode(65 + question.solution.answer_index)}{question.options[question.solution.answer_index] ? ` — ${question.options[question.solution.answer_index]}` : ""}</strong>}
        <p>{question.solution.explanation}</p>
      </div>
      <footer><a href={question.source_url} target="_blank" rel="noreferrer">Check original question <ExternalLink size={12} /></a></footer>
    </article>)}
    {result.has_more && current && <button type="button" className={s.continueSolutions} disabled={disabled} onClick={onContinue}>
      {solutionContinuation(result.next_number, result.range_end ?? result.paper?.total ?? result.next_number)}<ArrowRight size={15} />
    </button>}
    {result.status === "solutions" && !result.has_more && <p className={s.pyqCoverage}>End of this range. Any uncertain answers or missing source material still need review.</p>}
  </section>;
}
