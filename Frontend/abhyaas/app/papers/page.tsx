import { ArrowRight, Calendar, ChevronDown, Clock3, FileCheck2, FileText, ShieldCheck } from "lucide-react";
import AppShell from "../components/AppShell";

const paperTypes = [
  { title: "English paper", description: "Review questions, answers and concise language explanations.", track: "All CDS tracks" },
  { title: "General Knowledge paper", description: "Study topic-linked solutions across the complete GK paper.", track: "All CDS tracks" },
  { title: "Elementary Mathematics paper", description: "Work through solved questions or attempt the full timed paper.", track: "IMA · INA · AFA" },
];

export default function PapersPage() {
  return <AppShell active="Previous papers"><main className="workspace papers-workspace">
    <header className="workspace-header"><div><span className="workspace-kicker">Learn from the real examination</span><h1>Previous papers</h1><p>Read structured solutions or attempt a complete paper under timed conditions.</p></div><div className="workspace-badge"><FileCheck2 size={15} /> Paper archive</div></header>
    <section className="paper-filters"><button><Calendar size={15} /> Select year <ChevronDown size={14} /></button><button><ShieldCheck size={15} /> All academies <ChevronDown size={14} /></button><span>Choose filters to open a specific paper.</span></section>
    <section className="paper-type-grid">{paperTypes.map((paper, index) => <article key={paper.title}><header><span>0{index + 1}</span><FileText size={23} /></header><small>{paper.track}</small><h2>{paper.title}</h2><p>{paper.description}</p><div className="paper-actions"><button>View solutions <ArrowRight size={15} /></button><button><Clock3 size={15} /> Timed mock</button></div></article>)}</section>
    <section className="paper-method"><div><span className="workspace-kicker">Two ways to use a paper</span><h2>Study it. Then simulate it.</h2></div><div><article><strong>01 · Review mode</strong><p>Move question by question with the solved answer and a short explanation.</p></article><article><strong>02 · Mock mode</strong><p>Hide solutions, run the timer, and receive a summary after submission.</p></article></div></section>
  </main></AppShell>;
}
