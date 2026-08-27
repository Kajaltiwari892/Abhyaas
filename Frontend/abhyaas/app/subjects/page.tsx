"use client";

import { ArrowRight, BookA, BookOpen, FlaskConical, Globe2, Landmark, Languages, Sigma } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import AppShell from "../components/AppShell";
import { ApiError } from "@/lib/auth-api";
import { getSubjects, type Subject } from "@/lib/study-api";

const foundations = [{ icon: Landmark, label: "Humanities" }, { icon: FlaskConical, label: "Science" }, { icon: BookA, label: "NCERT foundations" }];
const subjectIcons = { english: Languages, "general-knowledge": Globe2, "elementary-mathematics": Sigma };

export default function SubjectsPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    getSubjects().then(setSubjects).catch((reason: unknown) => setError(reason instanceof ApiError ? reason.message : "Subjects could not be loaded."));
  }, []);

  return <AppShell active="Subjects"><main className="workspace subjects-workspace">
    <header className="workspace-header"><div><span className="workspace-kicker">Syllabus, made navigable</span><h1>Subjects</h1><p>Choose a subject, open a topic, and move directly into focused practice.</p></div><div className="workspace-badge"><BookOpen size={15} /> CDS syllabus</div></header>
    {error && <p className="workspace-message is-error">{error}</p>}
    {!error && subjects.length === 0 && <p className="workspace-message">Loading the CDS syllabus…</p>}
    <section className="subject-page-grid">{subjects.map((subject, index) => {
      const Icon = subjectIcons[subject.slug as keyof typeof subjectIcons] ?? BookOpen;
      return <article className="subject-page-card" key={subject.id}><header><span>0{index + 1}</span><Icon size={25} /></header><h2>{subject.name}</h2><p>{subject.description}</p><div className="topic-chip-grid">{subject.topics.map(topic => <Link href={`/practice?subject=${subject.slug}&topic=${topic.slug}`} key={topic.id}>{topic.name}<ArrowRight size={13} /></Link>)}</div></article>;
    })}</section>
    <section className="foundation-strip"><div><span className="workspace-kicker">Content approach</span><h2>Strong foundations before shortcuts.</h2><p>Core explanations are organised around the CDS syllabus and connected directly to practice.</p></div><div className="foundation-items">{foundations.map(({ icon: Icon, label }) => <span key={label}><Icon size={18} />{label}</span>)}</div></section>
  </main></AppShell>;
}
