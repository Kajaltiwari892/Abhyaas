"use client";

import { Sparkles } from "lucide-react";
import type { PracticeResult } from "@/lib/study-api";
import s from "./doubt-solver.module.css";

export default function PracticeResults({ result }: { result: PracticeResult }) {
  if (result.kind !== "practice") return null;
  return <section className={s.pyqResults} aria-label="Generated practice set">
    <div className={s.pyqFilters}>
      <span><Sparkles size={11} /> Generated practice</span><span>{result.topic}</span>
      <span>{result.returned} / {result.target} questions ready</span>
      {!result.complete && <span>Partial set</span>}
    </div>
    <p className={s.pyqCoverage}>All {result.returned} questions are below. Answers are hidden until you choose to reveal them. These questions and solutions are AI-generated, not official PYQs or verified answer keys.</p>
    {result.questions.map(question => <article className={s.pyqCard} key={question.number} aria-label={`Practice question ${question.number}`}>
      <header><span>Practice · {result.topic}</span><strong>Q{question.number}</strong></header>
      <p className={s.pyqPrompt}>{question.prompt}</p>
      <ol className={s.pyqOptions} type="A">{question.options.map((option,index)=><li key={index}>{option}</li>)}</ol>
      <details className={s.pyqKey}><summary>Reveal answer & explanation</summary>
        <p>Answer: {String.fromCharCode(65 + question.correct_index)}</p>
        <p className={s.pyqDirections}>{question.explanation}</p>
        <small>AI reasoning · not an official answer key</small>
      </details>
    </article>)}
  </section>;
}
