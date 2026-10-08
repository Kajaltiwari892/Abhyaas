"use client";

import { BookOpen, ExternalLink, Sparkles } from "lucide-react";
import type { PyqResult } from "@/lib/study-api";
import s from "./doubt-solver.module.css";

export default function PyqResults({ result, loading, onExplain }: {
  result: PyqResult; loading: boolean; onExplain: (id: string, label: string) => void;
}) {
  if (result.kind !== "pyq") return null;
  return <section className={s.pyqResults} aria-label="Questions from the paper archive">
    <div className={s.pyqFilters}><span>{result.query.years.join(", ") || "All indexed years"}</span><span>{result.query.cycle ? `CDS ${result.query.cycle}` : "Both CDS cycles"}</span></div>
    {result.questions.map((question) => <article className={s.pyqCard} key={question.id}>
      <header><span>CDS {question.cycle} · {question.year} · {question.subject}</span><strong>Q{question.number}</strong></header>
      <div className={s.pyqBadges}><span>{question.text_reviewed ? "Text checked against source" : "Compare with original"}</span><span>{question.answer_basis === "reviewed" ? "Checked practice answer" : question.answer_basis === "provisional" ? "Provisional answer" : question.answer_verified ? "Official answer available" : "Answer being checked"}</span></div>
      {!!question.topics.length && <small className={s.pyqTopic}>{question.topics.join(" · ")}</small>}
      {question.passage && <details className={s.pyqPassage}><summary>Read the passage</summary><p>{question.passage}</p></details>}
      {question.directions && <p className={s.pyqDirections}>{question.directions}</p>}
      <p className={s.pyqPrompt}>{question.prompt}</p>
      <ol className={s.pyqOptions} type="A">{question.options.map((option, index) => <li key={index}>{option}</li>)}</ol>
      {question.has_visual && <p className={s.pyqDirections}>This question includes a figure. Open the original page to see it.</p>}
      <footer>
        {question.source_page_url && <a href={question.source_page_url} target="_blank" rel="noreferrer"><BookOpen size={12} /> Original page {question.source_page}</a>}
        <a href={question.source_url} target="_blank" rel="noreferrer">UPSC paper <ExternalLink size={12} /></a>
        <button disabled={loading || question.has_visual} title={question.has_visual ? "Attach the original diagram to ask for an explanation" : "Get an AI explanation of this exact question"} onClick={() => onExplain(question.id, `Explain CDS ${question.cycle} ${question.year} ${question.subject} question ${question.number}.`)}><Sparkles size={12} /> Explain</button>
      </footer>
      {(question.answer_scorable ?? question.answer_verified) && question.correct_index !== null && <details className={s.pyqKey}><summary>Reveal answer</summary><p>Answer: {String.fromCharCode(65 + question.correct_index)}</p>{question.explanation && <p>{question.explanation}</p>}</details>}
    </article>)}
    <p className={s.pyqCoverage}>Search coverage: {result.indexed_questions} of {result.catalog_questions} catalogued questions have searchable text within these year/subject filters. Chapter tags are editorial/search aids, not UPSC labels. More text and topic review may reveal additional matches.</p>
  </section>;
}
