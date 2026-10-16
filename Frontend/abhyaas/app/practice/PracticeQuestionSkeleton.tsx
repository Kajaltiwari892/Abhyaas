import s from "./practice.module.css";
import styles from "./PracticeQuestionSkeleton.module.css";

export default function PracticeQuestionSkeleton({
  subject, topic, count, prepared, delayed = false,
}: { subject?: string; topic?: string; count?: number; prepared?: number; delayed?: boolean }) {
  return <section className={`${s.session} ${styles.skeleton}`} aria-busy="true" aria-label="Preparing practice questions">
    <div className={styles.status} role="status" aria-live="polite">
      <strong>{delayed ? "Still preparing your questions…" : count ? `Preparing your ${count}-question quiz…` : "Opening your questions…"}</strong>
      <span>{[subject, topic].filter(Boolean).join(" · ") || "Your questions will open here when ready."}</span>
      {prepared !== undefined && <><small>{prepared} of {count ?? 50} questions ready. You can retry without starting over.</small><progress className={styles.progress} aria-label="Questions prepared" value={prepared} max={count ?? 50} /></>}
      {delayed && <small>New questions can take a little longer. You can go back and try again later.</small>}
    </div>
    <div className={styles.preview} aria-hidden="true">
      <div className={styles.toolbar}><span className={`${styles.block} ${styles.label}`} /><span className={`${styles.block} ${styles.label}`} /></div>
      <div className={styles.navigator}>{Array.from({ length: 10 }, (_, i) => <span key={i} className={`${styles.block} ${styles.square}`} />)}</div>
      <div className={styles.question}>
        <span className={`${styles.block} ${styles.label}`} />
        <div className={styles.prompt}><span className={styles.block} /><span className={styles.block} /><span className={styles.block} /></div>
        <div className={styles.options}>{[0, 1, 2, 3].map(i => <div key={i} className={styles.option}><span className={`${styles.block} ${styles.square}`} /><span className={styles.block} /></div>)}</div>
      </div>
      <div className={styles.footer}><span className={`${styles.block} ${styles.action}`} /><span className={`${styles.block} ${styles.action}`} /></div>
    </div>
  </section>;
}
