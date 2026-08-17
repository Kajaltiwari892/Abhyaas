"use client";

import {
  ArrowRight, BarChart3, BookOpen, Bot, BrainCircuit, CalendarCheck,
  ChevronRight, FileCheck2, GraduationCap, Headphones, Home as HomeIcon, Menu,
  MessageSquareText, Mic, ShieldCheck, Swords, Target, X,
} from "lucide-react";
import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import academyCollage from "../assets/img1.jpg";
import honourBackdrop from "../assets/img3.jpg";
import heroBackdrop from "../assets/img4.jpg";
import ExamSwitcher from "./components/ExamSwitcher";

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
  { code: "MAT", name: "Elementary Mathematics", topics: "Arithmetic · Algebra · Geometry · Trigonometry", icon: Target, note: "IMA · INA · AFA only" },
];

export default function Home() {
  const [menuOpen, setMenuOpen] = useState(false);

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
        <Link className="nav-cta" href="/practice">Start practising <ArrowRight size={15} /></Link>
        <button className="menu-button" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle navigation" aria-expanded={menuOpen}>
          {menuOpen ? <X /> : <Menu />}
        </button>
        {menuOpen && <nav className="mobile-menu" aria-label="Mobile navigation">
          {navItems.map(([label, href]) => <Link key={href} href={href} onClick={() => setMenuOpen(false)}>{label}<ChevronRight size={16} /></Link>)}
        </nav>}
      </header>

      <section className="hero" id="top">
        <Image className="hero-image" src={heroBackdrop} alt="CDS cadets celebrating together" fill priority sizes="100vw" />
        <div className="hero-image-overlay" />
        <div className="hero-grid" />
        <div className="hero-copy">
          <div className="eyebrow"><span /> IMA · INA · AFA · OTA</div>
          <h1 className="hero-title"><span>Everything you need for CDS.</span><em>One place. Zero cost.</em></h1>
          <p className="hero-lede">Daily practice, previous papers and clear doubt-solving—built for serious CDS preparation.</p>
          <div className="hero-actions">
            <Link className="button button-primary" href="/practice">Start practising <ArrowRight size={17} /></Link>
            <Link className="button button-quiet" href="/exam-info">Explore the platform <ChevronRight size={17} /></Link>
          </div>
        </div>
      </section>

      <section className="motivation-strip" aria-label="Motivational note">
        <span className="strip-icon"><Target size={18} /></span>
        <p>“You do not need a perfect plan. You need a plan you can return to tomorrow.”</p>
        <span className="strip-rule" /><small>NOTE 01 / CONSISTENCY</small>
      </section>

      <section className="section features-section" id="practice">
        <div className="section-heading">
          <div><span className="kicker">Your preparation system</span><h2>Less searching.<br />More studying.</h2></div>
          <p>Everything here has one job: help you understand, practise and improve without switching between scattered resources.</p>
        </div>
        <div className="feature-grid">
          {features.map(({ number, icon: Icon, title, copy, label, href }) => <article className="feature-card" key={title}>
            <span className="card-number">{number}</span><span className="feature-icon"><Icon size={25} strokeWidth={1.7} /></span>
            <h3>{title}</h3><p>{copy}</p><Link href={href}>{label} <ArrowRight size={15} /></Link>
          </article>)}
        </div>
      </section>

      <section className="dark-section" id="doubt-solver">
        <div className="dark-section-inner">
          <div className="ai-demo">
            <div className="demo-topbar"><div><span className="live-dot" /> ABHYAAS AI</div><span>SOURCE-GROUNDED ANSWERS</span></div>
            <div className="student-query">Why does the monsoon first reach Kerala?<small>YOUR QUESTION</small></div>
            <div className="ai-answer"><span className="answer-icon"><Bot size={18} /></span><div>
              <strong>Because of its position and the path of the winds.</strong>
              <p>The Arabian Sea branch of the southwest monsoon meets India’s western coast at Kerala first. The Western Ghats then force the moisture-laden air to rise and cool, causing heavy rainfall.</p>
              <div className="source-tag"><BookOpen size={13} /> Source: NCERT Geography · Class 11</div>
            </div></div>
            <div className="demo-input"><Mic size={18} /><span>Ask a follow-up question...</span><button aria-label="Send question"><ArrowRight size={17} /></button></div>
          </div>
          <div className="ai-copy">
            <span className="kicker kicker-light">Doubt solver</span><h2>Ask naturally.<br />Understand clearly.</h2>
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
        <div className="section-heading compact">
          <div><span className="kicker">Syllabus, made navigable</span><h2>Choose a subject.<br />Pick up where you left off.</h2></div>
          <p>Go from syllabus to topic-level practice without losing your place.</p>
        </div>
        <div className="subject-list">
          {subjects.map(({ code, name, topics, icon: Icon, note }) => <Link href="/subjects" className="subject-row" key={name}>
            <span className="subject-code">{code}</span><span className="subject-icon"><Icon size={23} /></span>
            <span className="subject-copy"><strong>{name}</strong><small>{topics}</small></span>
            {note && <span className="track-note">{note}</span>}<span className="round-arrow"><ArrowRight size={17} /></span>
          </Link>)}
        </div>
      </section>

      <section className="exam-section" id="exam-info">
        <div className="exam-card">
          <div className="exam-copy"><span className="kicker">Know the path</span><h2>One exam.<br />Five academy tracks.</h2>
            <p>Understand eligibility, paper pattern and the full selection process before you begin.</p>
            <Link className="button button-primary" href="/exam-info">Explore exam information <ArrowRight size={16} /></Link>
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
        <div className="progress-preview"><div className="preview-head"><span>WEEKLY OVERVIEW</span><span>YOUR DATA ONLY</span></div>
          <div className="chart-area"><div className="chart-labels"><span>100%</span><span>75%</span><span>50%</span><span>25%</span></div>
            <svg viewBox="0 0 600 210" role="img" aria-label="Empty accuracy chart awaiting practice data"><defs><linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#1c604a" stopOpacity=".2" /><stop offset="100%" stopColor="#1c604a" stopOpacity="0" /></linearGradient></defs><path className="chart-grid-line" d="M0 20H600M0 70H600M0 120H600M0 170H600" /><path className="chart-placeholder" d="M0 162 C90 158 135 132 210 138 S330 95 400 105 S500 68 600 72" /></svg>
            <div className="empty-chart"><BarChart3 size={20} /><span>Your chart begins after your first practice set.</span></div>
          </div>
        </div>
      </section>

      <section className="closing-section">
        <Image className="closing-image" src={honourBackdrop} alt="Indian military ceremony with the Serve with Honour insignia" fill sizes="100vw" />
        <div className="closing-image-overlay" />
        <span className="closing-symbol"><ShieldCheck size={32} /></span>
        <h2>Preparation should depend on your discipline—<em>not your ability to pay.</em></h2>
        <p>Start small. Return tomorrow. Let the work compound.</p>
        <Link className="button button-gold" href="/practice">Begin your preparation <ArrowRight size={17} /></Link>
      </section>

      <footer><div className="footer-main">
        <div className="footer-brand"><span className="brand-mark"><ShieldCheck size={19} /></span><div><strong>ABHYAAS</strong><small>A free CDS preparation platform.</small></div></div>
        <div className="footer-links"><Link href="/exam-info">Exam info</Link><Link href="/subjects">Subjects</Link><Link href="/practice">Practice</Link><Link href="/doubt-solver">Doubt solver</Link></div>
        <div className="footer-links"><Link href="/about">About</Link><a href="mailto:hello@abhyaas.example">Contact</a><a href="#disclaimer">Disclaimer</a></div>
      </div><div className="footer-bottom" id="disclaimer"><span>Student-built, non-official CDS preparation tool.</span><span>Always verify current details with the official UPSC notification.</span></div></footer>

      <nav className="bottom-nav" aria-label="Quick navigation">
        <a href="#top"><HomeIcon size={20} /><span>Home</span></a><Link href="/practice"><Target size={20} /><span>Practice</span></Link>
        <Link href="/doubt-solver" className="bottom-nav-main"><Bot size={23} /><span>Ask AI</span></Link>
        <Link href="/papers"><FileCheck2 size={20} /><span>Papers</span></Link><Link href="/progress"><BarChart3 size={20} /><span>Progress</span></Link>
      </nav>
    </main>
  );
}
