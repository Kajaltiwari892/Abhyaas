import { AlertTriangle, ArrowRight, BookOpen, CheckCircle2, ChevronRight, HeartPulse, Medal, Shield, Users } from "lucide-react";
import AppShell from "../components/AppShell";
import PrimaryButton from "@/components/ui/primary-button";

const academies = [
  { code: "IMA", name: "Indian Military Academy", branch: "Army", detail: "Permanent Commission training for the Indian Army." },
  { code: "INA", name: "Indian Naval Academy", branch: "Navy", detail: "Officer training for service in the Indian Navy." },
  { code: "AFA", name: "Air Force Academy", branch: "Air Force", detail: "Training pathway for commissioned Air Force officers." },
  { code: "OTA · M", name: "Officers Training Academy", branch: "Men", detail: "Short Service Commission training through the OTA track." },
  { code: "OTA · W", name: "Officers Training Academy", branch: "Women", detail: "Short Service Commission pathway for women candidates." },
];

const stages = [
  { icon: BookOpen, title: "Written examination", text: "UPSC-conducted objective papers based on the selected academy track." },
  { icon: Users, title: "SSB interview", text: "A multi-stage assessment of officer-like qualities and suitability." },
  { icon: HeartPulse, title: "Medical examination", text: "Service-specific medical standards are assessed." },
  { icon: Medal, title: "Final merit", text: "Final allocation depends on merit, eligibility, preference and vacancies." },
];

export default function ExamInfoPage() {
  return <AppShell active="Exam info"><main className="workspace info-workspace">
    <header className="workspace-header"><div><span className="workspace-kicker">Understand the examination</span><h1>CDS exam information</h1><p>A clear overview of academy routes, papers and the selection journey.</p></div><div className="workspace-badge"><Shield size={15} /> UPSC pathway</div></header>
    <section className="official-notice"><AlertTriangle size={17} /><div><strong>Use this as a preparation guide.</strong><span>Age limits, dates, vacancies and detailed eligibility can change. Always verify them in the latest official UPSC notification.</span></div></section>
    <section className="academy-route-grid">{academies.map((item, index) => <article key={item.code}><span className="route-index">0{index + 1}</span><span className="route-emblem"><Shield size={20} /></span><small>{item.branch}</small><h2>{item.code}</h2><h3>{item.name}</h3><p>{item.detail}</p><PrimaryButton href="/login?next=/exam-info" size="sm">View eligibility <ChevronRight size={15} /></PrimaryButton></article>)}</section>
    <section className="exam-pattern-card"><header><div><span>Written exam structure</span><small>Paper availability depends on academy choice</small></div></header><div className="pattern-table"><div className="pattern-head"><span>Track</span><span>English</span><span>General Knowledge</span><span>Mathematics</span></div><div><strong>IMA · INA · AFA</strong><span><CheckCircle2 size={15} /> Included</span><span><CheckCircle2 size={15} /> Included</span><span><CheckCircle2 size={15} /> Included</span></div><div><strong>OTA</strong><span><CheckCircle2 size={15} /> Included</span><span><CheckCircle2 size={15} /> Included</span><span className="not-applicable">Not applicable</span></div></div></section>
    <section className="selection-section"><span className="workspace-kicker">Selection journey</span><h2>From application to academy</h2><div className="selection-stage-grid">{stages.map(({ icon: Icon, title, text }, index) => <article key={title}><span className="stage-number">0{index + 1}</span><Icon size={22} /><h3>{title}</h3><p>{text}</p>{index < stages.length - 1 && <ArrowRight className="stage-connector" size={19} />}</article>)}</div></section>
  </main></AppShell>;
}
