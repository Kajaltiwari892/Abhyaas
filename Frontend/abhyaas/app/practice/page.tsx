"use client";

import { Bookmark, ChevronDown, Clock3, Filter, Pause, Play, RotateCcw, ShieldCheck } from "lucide-react";
import { useState } from "react";
import AppShell from "../components/AppShell";
import PrimaryButton from "@/components/ui/primary-button";

const options = ["The error is in part A", "The error is in part B", "The error is in part C", "No error"];

export default function PracticePage() {
  const [started, setStarted] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [paused, setPaused] = useState(false);
  const [marked, setMarked] = useState(false);
  return <AppShell active="Practice"><main className="workspace practice-workspace">
    <header className="workspace-header"><div><span className="workspace-kicker">Build the daily habit</span><h1>Daily practice</h1><p>A focused question set with exam-like controls and a calm review flow.</p></div><div className="workspace-badge"><ShieldCheck size={15} /> Practice mode</div></header>
    <section className="practice-controls"><button><Filter size={15} /> English <ChevronDown size={14} /></button><button>All topics <ChevronDown size={14} /></button><span /><div className="practice-timer"><Clock3 size={16} /><small>Time remaining</small><strong>{started ? "29:42" : "30:00"}</strong><button onClick={() => setPaused(!paused)}>{paused ? <Play size={15} /> : <Pause size={15} />}</button></div></section>
    {!started ? <section className="practice-start"><span><Play size={26} /></span><h2>Today’s practice is ready</h2><p>Questions will be shown one at a time. You can pause the timer, mark questions for review, and revisit them before submitting.</p><div><small>Subject</small><strong>English</strong><small>Set length</small><strong>10 questions</strong><small>Timer</small><strong>30 minutes</strong></div><PrimaryButton href="/login?next=/practice">Start practice <Play size={16} /></PrimaryButton></section> : <section className="question-shell"><header><span>Question 01 <small>/ 10</small></span><button className={marked ? "marked" : ""} onClick={() => setMarked(!marked)}><Bookmark size={15} /> {marked ? "Marked" : "Mark for review"}</button></header><div className="question-body"><span className="question-topic">English · Error spotting</span><h2>Identify the part of the sentence that contains an error:</h2><p><b>A.</b> Neither of the officers <b>B.</b> were willing to accept <b>C.</b> responsibility for the delay.</p><div className="mcq-options">{options.map((option, index) => <button className={selected === index ? "selected" : ""} onClick={() => setSelected(index)} key={option}><span>{String.fromCharCode(65 + index)}</span>{option}</button>)}</div></div><footer><button onClick={() => { setSelected(null); setStarted(false); }}><RotateCcw size={15} /> Leave set</button><div><button className="secondary-question-button">Previous</button><PrimaryButton href="/login?next=/practice" className="next-question-button" size="sm" disabled={selected === null}>Save & next</PrimaryButton></div></footer></section>}
  </main></AppShell>;
}
