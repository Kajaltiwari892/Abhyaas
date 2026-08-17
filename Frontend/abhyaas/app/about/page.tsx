import Image from "next/image";
import { BookOpen, Heart, ShieldCheck, Target, Users } from "lucide-react";
import honourImage from "../../assets/img2.jpg";
import AppShell from "../components/AppShell";

export default function AboutPage() {
  return <AppShell active="About"><main className="workspace about-workspace">
    <header className="about-hero"><Image src={honourImage} alt="Indian soldiers holding the national flag" fill priority sizes="(max-width: 850px) 100vw, calc(100vw - 224px)" /><div className="about-hero-overlay"/><div><span className="workspace-kicker">Why Abhyaas exists</span><h1>Good preparation should be accessible.</h1><p>Built from the experience of facing the same scattered-resources problem as every serious aspirant.</p></div></header>
    <section className="origin-grid"><div><span className="workspace-kicker">The origin</span><h2>One focused place instead of ten disconnected ones.</h2></div><div><p>CDS preparation often means moving between paid apps, random PDFs, video playlists and incomplete notes. Abhyaas is being built to bring those essential study workflows into one disciplined, reliable space.</p><p>The objective is simple: help aspirants learn from sound foundations, practise consistently, understand their mistakes and ask for help without a financial barrier.</p></div></section>
    <section className="value-grid"><article><BookOpen size={21}/><h3>Clarity over clutter</h3><p>Every screen should help you study, not keep you scrolling.</p></article><article><Target size={21}/><h3>Consistency over intensity</h3><p>Small daily work matters more than occasional bursts.</p></article><article><Heart size={21}/><h3>Access over advantage</h3><p>Financial constraints should not decide who prepares well.</p></article><article><ShieldCheck size={21}/><h3>Honesty over hype</h3><p>No fake results, urgency, testimonials or activity numbers.</p></article></section>
    <section className="about-closing"><Users size={25}/><h2>Built by an aspirant, for aspirants.</h2><p>Abhyaas is a student-built, non-official preparation tool. Official UPSC material remains the final authority for examination details.</p></section>
  </main></AppShell>;
}
