import styles from "./PaperQuestionSkeleton.module.css";

export default function PaperQuestionSkeleton({ subject }: { subject: string }) {
  return <>
    <div className={styles.status} role="status" aria-live="polite">Preparing your {subject} questions…</div>
    <div className="paper-question-layout" aria-hidden="true">
      <div className="paper-question-panel">
        <div className={`paper-question-toolbar ${styles.toolbar}`}>
          <span className={`${styles.block} ${styles.selector}`} />
          <span className={`${styles.block} ${styles.label}`} />
        </div>
        <div className="paper-question-content">
          <div className={`paper-sheet ${styles.sheet}`}>
            <span className={`${styles.block} ${styles.label}`} />
            <div className={styles.prompt}>
              <span className={styles.block} /><span className={styles.block} /><span className={styles.block} />
            </div>
            <div className={styles.options}>
              {[0, 1, 2, 3].map((option) => <div className={styles.option} key={option}>
                <span className={`${styles.block} ${styles.circle}`} /><span className={styles.block} />
              </div>)}
            </div>
          </div>
        </div>
        <footer><span className={`${styles.block} ${styles.action}`} /><span className={`${styles.block} ${styles.action}`} /></footer>
      </div>
    </div>
  </>;
}
