"use client";

import { Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { requestFeedback } from "./request-feedback";
import s from "./doubt-solver.module.css";

export default function RequestStatus({ hasImage = false }: { hasImage?: boolean }) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const started = performance.now();
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((performance.now() - started) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  const feedback = requestFeedback(elapsedSeconds, hasImage);
  return <div className={s.thinking}>
    <span aria-hidden="true"><Sparkles size={16} /></span>
    <div className={s.requestFeedback} role="status" aria-live="polite" aria-busy="false">
      <div>{feedback.label}<span className={s.waitDots} aria-hidden="true"><i /><i /><i /></span></div>
      {feedback.detail && <p>{feedback.detail}</p>}
    </div>
    {feedback.elapsed && <small className={s.elapsedWait} aria-hidden="true">{feedback.elapsed}</small>}
  </div>;
}
