"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Anchor, ArrowDown, ArrowRight, ArrowUpRight, BookOpen, Calculator, Check, ChevronDown, Clock3, Compass, FileText, GraduationCap, HeartPulse, Info, MapPin, Medal, Plane, ShieldCheck, Swords, Target, Users } from "lucide-react";
import { getPreparationTarget } from "@/lib/academy-preference";
import { useAuth } from "../components/AuthProvider";
import imaPhoto from "../../assets/img6.jpg";
import { academies, examSource, getAcademyGuide, type AcademyId } from "./exam-guide-data";
import styles from "./exam-info.module.css";

const academyIcons = { ima: Swords, ina: Anchor, afa: Plane, ota: ShieldCheck };
const paperIcons = { english: BookOpen, gk: Compass, maths: Calculator };
const stages = [
  { icon: FileText, title: "Written exam", text: "Build your foundation and qualify in the papers for your route." },
  { icon: Users, title: "SSB assessment", text: "Screening, psychology tests, group tasks and an interview." },
  { icon: HeartPulse, title: "Medical review", text: "Meet the medical standards set for your chosen service." },
  { icon: Medal, title: "Merit & joining", text: "Your results, medical fitness and academy choices decide selection, based on available seats." },
];

export default function ExamGuide() {
  const { user, status, saveTargetAcademy } = useAuth();
  const [exploring, setExploring] = useState<AcademyId>();
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ text: string; error: boolean }>();
  const savedTarget = getPreparationTarget(user?.target_academy);
  const selected = exploring ?? (savedTarget ? user!.target_academy! : "ima");
  const { academy, papers, writtenMarks, writtenHours } = getAcademyGuide(selected);
  const AcademyIcon = academyIcons[academy.id];
  const isOta = selected === "ota";

  async function saveTarget(target: AcademyId | null) {
    if (saving) return;
    setSaving(true);
    setFeedback(undefined);
    try {
      await saveTargetAcademy(target);
      setFeedback({ error: false, text: target
        ? `${target.toUpperCase()} saved. Your subjects and practice now follow this target.`
        : "Target cleared. All subjects are available; your history is unchanged." });
    } catch (error) {
      setFeedback({ error: true, text: error instanceof Error ? error.message : "Could not save your target. Please try again." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}><Compass size={14} aria-hidden="true" /> YOUR CDS FIELD GUIDE</span>
          <h1>Know the exam.<br className={styles.mobileBreak} /> <em>Find your path.</em></h1>
          <p>Choose an academy to see who can apply, which papers to prepare for, and what comes next.</p>
        </div>
        <a className={styles.outlineLink} href={examSource.examinations} target="_blank" rel="noopener noreferrer">UPSC exam notices <ArrowUpRight size={16} aria-hidden="true" /><span className={styles.srOnly}> (opens in a new tab)</span></a>
      </header>

      <nav className={styles.sectionNav} aria-label="On this page">
        <a href="#academies"><span>01</span> Academy routes</a>
        <a href="#exam-pattern"><span>02</span> Exam pattern</a>
        <a href="#selection"><span>03</span> Selection</a>
        <a href="#questions"><span>04</span> Quick answers</a>
      </nav>

      <section id="academies" className={styles.section} aria-labelledby="academy-heading">
        <div className={styles.sectionHeading}>
          <div><span className={styles.sectionNumber}>01 / THE DESTINATION</span><h2 id="academy-heading">Which route interests you?</h2></div>
          <p>{savedTarget ? `Your target: ${savedTarget.code}. Select any academy to compare.` : "Select an academy to see its details below."}</p>
        </div>
        <div className={styles.academyGrid} role="group" aria-label="Choose an academy">
          {academies.map((item) => {
            const Icon = academyIcons[item.id];
            const active = selected === item.id;
            return (
              <button key={item.id} type="button" className={`${styles.academyCard} ${active ? styles.selectedCard : ""}`} aria-label={`Explore ${item.name} (${item.code})${user?.target_academy === item.id ? ", your saved target" : ""}`} aria-pressed={active} aria-controls="academy-details" onClick={() => { setExploring(item.id); setFeedback(undefined); }}>
                <span className={styles.academyPhoto}>
                  <Image src={item.id === "ima" ? imaPhoto : `/exam-info/${item.id}.jpg`} alt={item.photoAlt} fill sizes="(max-width: 600px) 50vw, (max-width: 1100px) 40vw, 24vw" loading="eager" className={item.id === "ota" ? styles.otaPhoto : undefined} />
                  <span className={styles.photoShade} />
                  <span className={styles.service}><Icon size={13} aria-hidden="true" />{item.service}</span>
                  <span className={styles.academyCode}>{item.code}</span>
                  {active && <span className={styles.selectedTick}><Check size={16} aria-hidden="true" /><span className={styles.srOnly}>Selected</span></span>}
                </span>
                <span className={styles.academyCopy}><strong>{item.name}</strong><small className={styles.entryTag}>{item.entry}</small><span><MapPin size={12} aria-hidden="true" /> {item.location}<span className={styles.cardArrow}>{user?.target_academy === item.id ? <><Target size={12} aria-hidden="true" /> Your target</> : <ArrowDown size={15} aria-hidden="true" />}</span></span></span>
              </button>
            );
          })}
        </div>

        <div className={styles.routeDetail} id="academy-details" role="region" aria-label={`${academy.code} route details`}>
          <div className={styles.routeSummary}>
            <span className={styles.routeIcon}><AcademyIcon size={23} aria-hidden="true" /></span>
            <div aria-live="polite" aria-atomic="true"><span className={styles.smallLabel}>{academy.code} · {academy.entry}</span><h3>{academy.commission}</h3><p>{papers.length} written papers <span>·</span> {writtenMarks} marks{isOta ? " · No Maths paper" : " · Includes Maths"}</p></div>
            <a href="#exam-pattern" className={styles.textLink}>See the papers <ArrowDown size={14} aria-hidden="true" /></a>
          </div>
          <div className={styles.routeRequirements}>
            <div><GraduationCap size={19} aria-hidden="true" /><div><h4>Education</h4><p>{academy.education}</p></div></div>
            <div><Clock3 size={19} aria-hidden="true" /><div><h4>Age: {academy.age}</h4><p>{academy.birthDates}</p></div></div>
          </div>
          <div className={styles.eligibility} aria-label={`Men and women: ${academy.code}`}>
            <div><h4><Users size={15} aria-hidden="true" /> Men</h4><p>{academy.menEligibility}</p></div>
            <div><h4><Users size={15} aria-hidden="true" /> Women</h4><p>{academy.womenEligibility}</p></div>
          </div>
          <div className={styles.targetActions}>
            <div><strong>{user?.target_academy === selected ? `${academy.code} is your study target` : `Prepare for ${academy.code}?`}</strong><p>{isOta ? "Focus on English and GK." : "Focus on English, GK and Elementary Mathematics."}</p></div>
            {status === "anonymous" ? <Link href="/login" className={styles.saveTarget}>Sign in to save a target <ArrowRight size={14} aria-hidden="true" /></Link> : <button type="button" className={styles.saveTarget} disabled={saving || status === "loading" || user?.target_academy === selected} onClick={() => void saveTarget(selected)}>{saving ? "Saving…" : status === "loading" ? "Loading account…" : user?.target_academy === selected ? <><Check size={15} aria-hidden="true" /> Target saved</> : <><Target size={15} aria-hidden="true" /> Set {academy.code} as my target</>}</button>}
            {savedTarget && <button type="button" className={styles.clearTarget} disabled={saving} onClick={() => void saveTarget(null)}>Clear saved target</button>}
          </div>
          {feedback && <p className={`${styles.targetFeedback} ${feedback.error ? styles.targetError : ""}`} role={feedback.error ? "alert" : "status"}>{feedback.text}</p>}
          <div className={styles.sourceNote}><Info size={14} aria-hidden="true" /><p>Age dates are for {examSource.label}. <a href={`${examSource.notification}#page=8`} target="_blank" rel="noopener noreferrer">Check the full eligibility rules before applying<ArrowUpRight size={12} aria-hidden="true" /><span className={styles.srOnly}> (opens PDF in a new tab)</span></a>.</p></div>
        </div>
      </section>

      <section id="exam-pattern" className={styles.section} aria-labelledby="pattern-heading">
        <div className={styles.sectionHeading}><div><span className={styles.sectionNumber}>02 / YOUR PREPARATION</span><h2 id="pattern-heading">{academy.code}: your written exam</h2></div><span className={styles.meta}><Clock3 size={14} aria-hidden="true" /> {writtenHours} hours across {papers.length} papers</span></div>
        <div className={styles.patternLayout}>
          <div className={styles.tableWrap}>
            <table className={styles.patternTable}>
              <caption className={styles.srOnly}>Written papers for {academy.name}</caption>
              <thead><tr><th scope="col">Subject</th><th scope="col">Marks</th><th scope="col">Time</th></tr></thead>
              <tbody>{papers.map((paper) => {
                const Icon = paperIcons[paper.id];
                return <tr key={paper.id}><th scope="row"><span className={styles.paperName}><span className={styles.paperIcon}><Icon size={19} aria-hidden="true" /></span><span>{paper.name}<small>{paper.hint}</small></span></span></th><td><span className={styles.marks}>{paper.marks}</span><small>marks</small></td><td>{paper.hours} hours</td></tr>;
              })}</tbody>
              <tfoot><tr><th scope="row">Written total</th><td>{writtenMarks} <small>marks</small></td><td>{writtenHours} <small>hours</small></td></tr></tfoot>
            </table>
            <p className={styles.markingNote}><Info size={14} aria-hidden="true" /> Wrong answer: lose ⅓ of that question’s marks. Unanswered: no penalty.</p>
          </div>
          <aside className={styles.prepNote}>
            <span className={styles.prepSymbol}><BookOpen size={28} strokeWidth={1.4} aria-hidden="true" /></span>
            <span className={styles.smallLabel}>YOUR {academy.code} PREPARATION</span>
            <h3>{isOta ? "Two" : "Three"} papers.<br /> One focused plan.</h3>
            <p>{isOta ? "Prepare English and General Knowledge. You don’t need a Maths paper for OTA." : "Prepare English, General Knowledge and Elementary Mathematics. Give each subject regular practice."}</p>
            <Link href="/subjects" className={styles.primaryLink}>Explore subjects <ArrowRight size={16} aria-hidden="true" /></Link>
            <Link href="/papers" className={styles.textLink}>Browse previous papers <ArrowUpRight size={15} aria-hidden="true" /></Link>
          </aside>
        </div>
      </section>

      <section id="selection" className={styles.section} aria-labelledby="selection-heading">
        <div className={styles.sectionHeading}><div><span className={styles.sectionNumber}>03 / THE JOURNEY</span><h2 id="selection-heading">Your path to {academy.code}</h2></div></div>
        <ol className={styles.journey}>{stages.map(({ icon: Icon, title, text }, index) => <li key={title}><div className={styles.journeyMarker}><Icon size={22} strokeWidth={1.5} aria-hidden="true" /><span>0{index + 1}</span></div><h3>{title}</h3><p>{index === 0 ? `Take ${papers.length} papers for ${writtenMarks} marks.` : index === 1 ? selected === "afa" ? "Complete the SSB assessment and the Computer Pilot Selection System test." : "Complete the screening, psychology tests, group tasks and interview." : index === 2 ? `Meet the medical standards for the ${academy.service}.` : text}</p></li>)}</ol>
        <p className={styles.journeyNote}>Apply through UPSC before the deadline. Final selection depends on your results, medical fitness and available seats.</p>
      </section>

      <section id="questions" className={`${styles.section} ${styles.faqSection}`} aria-labelledby="questions-heading">
        <div className={styles.sectionHeading}><div><span className={styles.sectionNumber}>04 / A LITTLE MORE CLARITY</span><h2 id="questions-heading">Good questions.<br /> Straight answers.</h2></div><p>The details that are easy to mix up.</p></div>
        <div className={styles.faqList}>
          <details><summary>Do I need Mathematics for OTA?<ChevronDown size={17} aria-hidden="true" /></summary><p>No. OTA has English and General Knowledge only. The IMA, INA and AFA written routes also include Elementary Mathematics.</p></details>
          <details><summary>Are OTA men’s and women’s papers different?<ChevronDown size={17} aria-hidden="true" /></summary><p>The written pattern is the same. Entry conditions and vacancies differ, so check the relevant men’s or women’s entry in your notification.</p></details>
          <details><summary>Which CDS academies are open to women?<ChevronDown size={17} aria-hidden="true" /></summary><p>Through CDS, women can apply to OTA for Short Service Commission. The IMA, INA and AFA entries listed here are for men.</p></details>
          <details><summary>How do I check whether I am eligible?<ChevronDown size={17} aria-hidden="true" /></summary><p>Check your date of birth, education, marital status and medical requirements in the UPSC notice for the exam you plan to take.</p><a className={styles.textLink} href={examSource.examinations} target="_blank" rel="noopener noreferrer">Open UPSC exam notices <ArrowUpRight size={14} aria-hidden="true" /><span className={styles.srOnly}> (opens in a new tab)</span></a></details>
          <details><summary>Where should I start practising?<ChevronDown size={17} aria-hidden="true" /></summary><p>Explore a previous paper to understand the format, then practise by subject. Use your results to decide what to revise next.</p><Link className={styles.textLink} href="/subjects">Go to practice <ArrowRight size={14} aria-hidden="true" /></Link></details>
        </div>
      </section>

      <div className={styles.footerNote}>
        <p><ShieldCheck size={15} aria-hidden="true" /><span><a href={examSource.notification} target="_blank" rel="noopener noreferrer">{examSource.label}<span className={styles.srOnly}> (PDF, opens in a new tab)</span></a><br /><small>Updated {examSource.reviewed}. Check the notice for your exam year.</small></span></p>
      </div>
    </main>
  );
}
