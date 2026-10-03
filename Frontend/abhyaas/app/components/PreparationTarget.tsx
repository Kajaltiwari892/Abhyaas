"use client";

import Link from "next/link";
import { ArrowRight, Target } from "lucide-react";
import { getPreparationTarget } from "@/lib/academy-preference";
import { useAuth } from "./AuthProvider";
import styles from "./preparation-target.module.css";

export default function PreparationTarget({ practiceLinks = false }: { practiceLinks?: boolean }) {
  const { user, status } = useAuth();
  const target = getPreparationTarget(user?.target_academy);
  if (status === "loading") return <div className={styles.loading} role="status">Loading your study target…</div>;
  return <section className={styles.panel} aria-label="Your preparation target">
    <div className={styles.row}>
      <span className={styles.icon}><Target size={20} aria-hidden="true" /></span>
      <div className={styles.copy}>
        <strong>{target ? `Your target · ${target.code}` : "Make this preparation yours"}</strong>
        <p>{target ? `${target.subjects.map((subject) => subject.name).join(" + ")}${target.code === "OTA" ? ". Maths is optional extra practice." : ". All three written subjects in focus."}` : "Choose an academy to focus your subjects and practice. You can change it anytime."}</p>
      </div>
      <Link href="/exam-info#academies">{target ? "Change target" : "Choose target"}<ArrowRight size={14} aria-hidden="true" /></Link>
    </div>
    {practiceLinks && target && <div className={styles.next}>
      <span>Start a focused set</span>
      <div>{target.subjects.map((subject) => <Link key={subject.slug} href={`/practice?subject=${subject.slug}`}>{subject.name}<ArrowRight size={13} aria-hidden="true" /></Link>)}</div>
      <small>Your stats and history below still include every subject, even after changing your target.</small>
    </div>}
  </section>;
}
