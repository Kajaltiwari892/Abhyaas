import { ArrowRight, BookA, BookOpen, FlaskConical, Globe2, Landmark, Languages, Sigma, ShieldAlert } from "lucide-react";
import Link from "next/link";
import AppShell from "../components/AppShell";

const subjects = [
  { name: "English", icon: Languages, description: "Build accuracy across language rules and comprehension.", topics: ["Grammar", "Vocabulary", "Comprehension", "Error spotting"] },
  { name: "General Knowledge", icon: Globe2, description: "Connect static subjects with relevant current awareness.", topics: ["History", "Geography", "Polity", "Economics", "General Science", "Current affairs"] },
  { name: "Elementary Mathematics", icon: Sigma, description: "Strengthen concepts and improve timed problem-solving.", note: "IMA · INA · AFA only", topics: ["Arithmetic", "Algebra", "Geometry", "Trigonometry", "Mensuration", "Statistics"] },
];

const foundations = [{ icon: Landmark, label: "Humanities" }, { icon: FlaskConical, label: "Science" }, { icon: BookA, label: "NCERT foundations" }];

export default function SubjectsPage() {
  return <AppShell active="Subjects"><main className="workspace subjects-workspace">
    <header className="workspace-header"><div><span className="workspace-kicker">Syllabus, made navigable</span><h1>Subjects</h1><p>Choose a subject, open a topic, and move directly into focused practice.</p></div><div className="workspace-badge"><BookOpen size={15} /> CDS syllabus</div></header>
    <section className="subject-page-grid">{subjects.map(({ name, icon: Icon, description, topics, note }, index) => <article className="subject-page-card" key={name}><header><span>0{index + 1}</span><Icon size={25} /></header><h2>{name}</h2><p>{description}</p>{note && <div className="subject-notice"><ShieldAlert size={14} /> {note}</div>}<div className="topic-chip-grid">{topics.map(topic => <Link href={`/practice?subject=${encodeURIComponent(name)}&topic=${encodeURIComponent(topic)}`} key={topic}>{topic}<ArrowRight size={13} /></Link>)}</div></article>)}</section>
    <section className="foundation-strip"><div><span className="workspace-kicker">Content approach</span><h2>Strong foundations before shortcuts.</h2><p>Core explanations are organised around standard books and syllabus topics, then connected to practice.</p></div><div className="foundation-items">{foundations.map(({ icon: Icon, label }) => <span key={label}><Icon size={18} />{label}</span>)}</div></section>
  </main></AppShell>;
}
