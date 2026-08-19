"use client";

import {
  ArrowRight, BarChart3, BookOpen, Bot, BrainCircuit, CalendarCheck,
  ChevronRight, FileCheck2, GraduationCap, Headphones, Home as HomeIcon, Menu,
  Mail, MessageSquareText, Mic, Swords, Target, X,
} from "lucide-react";
import { type FormEvent, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import academyCollage from "../assets/img1.jpg";
import honourBackdrop from "../assets/img3.jpg";
import heroBackdrop from "../assets/img4.jpg";
import ExamSwitcher from "./components/ExamSwitcher";
import { MinimalistTextEffect } from "@/components/ui/reveal-text";
import ScrollExpand from "@/components/ui/scroll-expand";
import ProgressAreaChart from "@/components/ui/progress-area-chart";
import PrimaryButton from "@/components/ui/primary-button";

const navItems = [
  ["Exam info", "/exam-info"], ["Subjects", "/subjects"], ["Practice", "/practice"],
  ["Doubt solver", "/doubt-solver"], ["Papers", "/papers"],
] as const;

const features = [
  { number: "01", icon: CalendarCheck, title: "Daily practice", copy: "Topic-wise question sets designed to turn preparation into a steady daily habit.", label: "Begin today’s set", href: "/practice" },
  { number: "02", icon: BrainCircuit, title: "AI doubt solver", copy: "Ask by text or voice and get a clear explanation with its source material attached.", label: "Ask a doubt", href: "/doubt-solver" },
  { number: "03", icon: FileCheck2, title: "Previous papers", copy: "Study solved CDS papers or attempt them in a focused, exam-like timed mode.", label: "Browse papers", href: "/papers" },
];

const subjects = [
  { code: "ENG", name: "English", topics: "Grammar · Vocabulary · Comprehension · Error spotting", icon: BookOpen },
  { code: "GK", name: "General Knowledge", topics: "History · Geography · Polity · Science · Current affairs", icon: GraduationCap },
  { code: "MAT", name: "Elementary Mathematics", topics: "Arithmetic · Algebra · Geometry · Trigonometry", icon: Target },
];

export default function Home() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [demoDraft, setDemoDraft] = useState("");
  const [demoQuestion, setDemoQuestion] = useState("Why does the monsoon first reach Kerala?");

  function submitDemoQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextQuestion = demoDraft.trim();
    if (!nextQuestion) return;
    setDemoQuestion(nextQuestion);
    setDemoDraft("");
  }

  return (
    <main>
      <header className="site-header">
        <a href="#top" className="brand" aria-label="Abhyaas home">
          <span className="brand-mark"><Swords size={19} strokeWidth={1.8} /></span>
          <span>ABHYAAS</span>
        </a>
        <ExamSwitcher />
        <nav className="desktop-nav" aria-label="Main navigation">
          {navItems.map(([label, href]) => <Link key={href} href={href}>{label}</Link>)}
        </nav>
        <PrimaryButton className="nav-cta" href="/login?next=/practice" size="sm">Start practising <ArrowRight size={15} /></PrimaryButton>
        <button className="menu-button" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle navigation" aria-expanded={menuOpen}>
          {menuOpen ? <X /> : <Menu />}
        </button>
        {menuOpen && <nav className="mobile-menu" aria-label="Mobile navigation">
          {navItems.map(([label, href]) => <Link key={href} href={href} onClick={() => setMenuOpen(false)}>{label}<ChevronRight size={16} /></Link>)}
        </nav>}
      </header>

      <section className="scroll-hero-section" id="top">
        <ScrollExpand
          src={heroBackdrop.src}
          alt="CDS cadets celebrating together"
          title={<MinimalistTextEffect text="capture the selfless spirit" duration={0.45} />}
          scrollHint="Scroll down to expand"
          startWidth={36}
          startHeight={48}
          startRadius={22}
          endRadius={0}
          mediaZoom={1.24}
          scrollDistance={1.08}
          holdDistance={1.35}
          smoothing={0.1}
          overlayScrim={0.78}
          useWindowScroll
        >
          <div className="scroll-hero-content">
            <span>IMA · INA · AFA · OTA</span>
            <h1><span>Everything you need for CDS.</span><em>One place. Zero cost.</em></h1>
            <p>Daily practice, previous papers and clear doubt-solving—built for serious CDS preparation.</p>
            <div className="scroll-hero-actions">
              <PrimaryButton href="/login?next=/practice" size="lg">Start practising <ArrowRight size={17} /></PrimaryButton>
              <Link className="button button-quiet" href="/login?next=/exam-info">Explore the platform <ChevronRight size={17} /></Link>
            </div>
          </div>
        </ScrollExpand>
      </section>

      <div className="home-stack-panel stack-panel-1 prep-stack">
        <section className="motivation-strip" aria-label="Motivational note">
          <span className="strip-icon"><Target size={18} /></span>
          <p>“You do not need a perfect plan. You need a plan you can return to tomorrow.”</p>
          <span className="strip-rule" /><small>NOTE 01 / CONSISTENCY</small>
        </section>

        <section className="section features-section" id="practice">
          <div className="section-heading">
            <div><span className="kicker">Why Abhyaas exists</span><h2>Good preparation should not feel scattered.</h2></div>
            <p>Useful free lessons, PDFs and notes are spread across dozens of places, while collecting every recommended book can become expensive. Abhyaas brings the essential preparation path together.</p>
          </div>
          <div className="prep-value-grid">
            <article><span>01 · The problem</span><h3>Too many disconnected resources</h3><p>Moving between videos, PDFs, notes and apps wastes time and makes it difficult to know what to study next.</p></article>
            <article><span>02 · What we organise</span><h3>Trusted foundations in one path</h3><p>Previous papers, NCERT-based concepts and coverage guided by standard CDS references across English, Polity and other subjects.</p></article>
            <article><span>03 · What you gain</span><h3>A clear daily preparation system</h3><p>Learn a topic, practise it, understand mistakes and return tomorrow without rebuilding your plan every day.</p></article>
          </div>
          <div className="feature-grid">
            {features.map(({ number, icon: Icon, title, copy, label, href }) => <article className="feature-card" key={title}>
              <span className="card-number">{number}</span><span className="feature-icon"><Icon size={25} strokeWidth={1.7} /></span>
              <h3>{title}</h3><p>{copy}</p><Link href={href}>{label} <ArrowRight size={15} /></Link>
            </article>)}
          </div>
        </section>
      </div>

      <section className="dark-section" id="doubt-solver">
        <div className="dark-section-inner">
          <div className="ai-demo">
            <div className="demo-topbar"><div><span className="live-dot" /> ABHYAAS AI</div><span>SOURCE-GROUNDED ANSWERS</span></div>
            <div className="student-query" aria-live="polite">{demoQuestion}<small>YOUR QUESTION</small></div>
            <div className="ai-answer"><span className="answer-icon"><Bot size={18} /></span><div>
              <strong>Because of its position and the path of the winds.</strong>
              <p>The Arabian Sea branch of the southwest monsoon meets India’s western coast at Kerala first. The Western Ghats then force the moisture-laden air to rise and cool, causing heavy rainfall.</p>
              <div className="source-tag"><BookOpen size={13} /> Source: NCERT Geography · Class 11</div>
            </div></div>
            <form className="demo-input" onSubmit={submitDemoQuestion}>
              <Mic size={18} aria-hidden="true" />
              <input value={demoDraft} onChange={(event) => setDemoDraft(event.target.value)} placeholder="Ask a follow-up question..." aria-label="Ask a follow-up question" />
              <button type="submit" aria-label="Send question" disabled={!demoDraft.trim()}><ArrowRight size={17} /></button>
            </form>
          </div>
          <div className="ai-copy">
            <span className="kicker kicker-light">Doubt solver</span><h2 className="ai-title-single">Ask naturally. Understand clearly.</h2>
            <p>When a concept does not click, ask in your own words. Abhyaas gives you a direct explanation and shows where the answer came from.</p>
            <ul>
              <li><MessageSquareText size={18} /><span><strong>Continue the conversation</strong>Ask follow-up questions in the same thread.</span></li>
              <li><Mic size={18} /><span><strong>Speak instead of typing</strong>Useful when you are revising on the move.</span></li>
              <li><Headphones size={18} /><span><strong>Listen to explanations</strong>Switch between reading and audio playback.</span></li>
            </ul>
            <Link className="text-link light-link" href="/doubt-solver">Try the doubt solver <ArrowRight size={16} /></Link>
          </div>
        </div>
      </section>

      <section className="section subjects-section" id="subjects">
        <div className="section-heading compact subjects-heading">
          <div><span className="kicker">Syllabus, made navigable</span><h2>Choose a subject.<br />Pick up where you left off.</h2></div>
        </div>
        <div className="subject-list">
          {subjects.map(({ code, name, topics, icon: Icon }) => <Link href="/subjects" className="subject-row" key={name}>
            <span className="subject-code">{code}</span><span className="subject-icon"><Icon size={23} /></span>
            <span className="subject-copy"><strong>{name}</strong><small>{topics}</small></span>
            <span className="round-arrow"><ArrowRight size={17} /></span>
          </Link>)}
        </div>
      </section>

      <section className="exam-section" id="exam-info">
        <div className="exam-card">
          <div className="exam-copy"><span className="kicker">Know the path</span><h2>One exam.<br />Five academy tracks.</h2>
            <p>Understand eligibility, paper pattern and the full selection process before you begin.</p>
            <PrimaryButton href="/login?next=/exam-info">Explore exam information <ArrowRight size={16} /></PrimaryButton>
          </div>
          <div className="academy-tracks" id="academy-tracks">
            {["IMA", "INA", "AFA", "OTA · MEN", "OTA · WOMEN"].map((item, index) => <div className="academy-item" key={item}><span>0{index + 1}</span><strong>{item}</strong><ChevronRight size={17} /></div>)}
          </div>
          <div className="academy-art" aria-hidden="true">
            <Image src={academyCollage} alt="" fill sizes="(max-width: 760px) 100vw, 260px" />
            <div className="academy-art-overlay" />
            <span>Service before self</span>
          </div>
        </div>
        <div className="selection-path"><span className="path-title">CDS selection path</span>
          {["Written exam", "SSB interview", "Medical exam", "Final merit"].map((item, index) => <div className="path-step" key={item}><span>{index + 1}</span><strong>{item}</strong>{index < 3 && <ArrowRight className="path-arrow" size={18} />}</div>)}
        </div>
      </section>

      <section className="section progress-section" id="papers">
        <div className="progress-copy"><span className="kicker">Progress that means something</span><h2>See what needs<br />your attention.</h2>
          <p>Your dashboard will use your actual practice history to reveal strengths, weak topics and accuracy over time—never invented activity.</p>
          <Link className="text-link" href="/progress">View progress dashboard <ArrowRight size={16} /></Link>
        </div>
        <ProgressAreaChart />
      </section>

      <section className="closing-section">
        <Image className="closing-image" src={honourBackdrop} alt="Indian military ceremony with the Serve with Honour insignia" fill sizes="100vw" />
        <div className="closing-image-overlay" />
        <div className="closing-content">
          <h2>Preparation should depend on your discipline—<em>not your ability to pay.</em></h2>
          <p>Start small. Return tomorrow. Let the work compound.</p>
          <PrimaryButton href="/login?next=/practice" size="lg">Begin your preparation <ArrowRight size={17} /></PrimaryButton>
        </div>
      </section>

      <footer className="site-footer">
        <div className="footer-main">
          <div className="footer-brand"><span className="brand-mark"><Swords size={19} /></span><div><strong>ABHYAAS</strong><small>Focused preparation for those who choose to serve.</small></div></div>
          <div className="footer-links"><span className="footer-label">Explore</span><Link href="/exam-info">Exam info</Link><Link href="/subjects">Subjects</Link><Link href="/practice">Practice</Link><Link href="/doubt-solver">Doubt solver</Link></div>
          <div className="footer-links"><span className="footer-label">Platform</span><Link href="/papers">Previous papers</Link><Link href="/progress">Progress</Link><Link href="/about">About</Link></div>
          <div className="footer-contact"><span className="footer-label">Questions or doubts?</span><p>Write to us anytime. We will get back to you as soon as possible.</p><a href="mailto:kanjal55567@gmail.com"><Mail size={16} />kanjal55567@gmail.com</a></div>
        </div>
        <a className="footer-wordmark" href="#top" aria-label="Back to the top">
          <svg viewBox="0 0 1200 232" role="img" aria-label="Abhyaas">
            <defs>
              <linearGradient id="footer-outline-gradient" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0" stopColor="#ff9933" />
                <stop offset=".3" stopColor="#ff9933" />
                <stop offset=".48" stopColor="#f4f5ef" />
                <stop offset=".58" stopColor="#f4f5ef" />
                <stop offset=".7" stopColor="#138808" />
                <stop offset="1" stopColor="#138808" />
              </linearGradient>
              <linearGradient id="footer-flow-gradient" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0" stopColor="#ff9933" />
                <stop offset=".3" stopColor="#ff9933" />
                <stop offset=".48" stopColor="#ffffff" />
                <stop offset=".58" stopColor="#ffffff" />
                <stop offset=".7" stopColor="#138808" />
                <stop offset="1" stopColor="#138808" />
              </linearGradient>
              <filter id="footer-word-glow" x="-10%" y="-35%" width="120%" height="170%">
                <feGaussianBlur stdDeviation="8" />
              </filter>
            </defs>
            <text className="footer-word-glow" x="600" y="211" textAnchor="middle" textLength="1150" lengthAdjust="spacingAndGlyphs">ABHYAAS</text>
            <text className="footer-word-outline" x="600" y="211" textAnchor="middle" textLength="1150" lengthAdjust="spacingAndGlyphs">ABHYAAS</text>
          </svg>
        </a>
      </footer>

      <nav className="bottom-nav" aria-label="Quick navigation">
        <a href="#top"><HomeIcon size={20} /><span>Home</span></a><Link href="/practice"><Target size={20} /><span>Practice</span></Link>
        <Link href="/doubt-solver" className="bottom-nav-main"><Bot size={23} /><span>Ask AI</span></Link>
        <Link href="/papers"><FileCheck2 size={20} /><span>Papers</span></Link><Link href="/progress"><BarChart3 size={20} /><span>Progress</span></Link>
      </nav>
    </main>
  );
}
