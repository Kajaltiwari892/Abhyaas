"use client";

import { motion, useReducedMotion } from "motion/react";
import { useRef, useState } from "react";

export function MinimalistTextEffect({
  text,
  duration = 0.45,
  delay = 0,
  className = "",
}: {
  text: string;
  duration?: number;
  delay?: number;
  className?: string;
}) {
  const rootRef = useRef<HTMLSpanElement>(null);
  const [hovered, setHovered] = useState(false);
  const reduceMotion = useReducedMotion();

  const updateShine = (event: React.PointerEvent<HTMLSpanElement>) => {
    const root = rootRef.current;
    if (!root) return;
    const rect = root.getBoundingClientRect();
    root.style.setProperty("--shine-x", `${event.clientX - rect.left}px`);
    root.style.setProperty("--shine-y", `${event.clientY - rect.top}px`);
  };

  return (
    <span
      ref={rootRef}
      className={`minimalist-text ${className}`}
      onPointerEnter={() => setHovered(true)}
      onPointerLeave={() => setHovered(false)}
      onPointerMove={updateShine}
    >
      <motion.span
        className="minimalist-text-base"
        initial={reduceMotion ? false : { opacity: 0, y: "0.34em", clipPath: "inset(0 0 100% 0)" }}
        animate={{ opacity: 1, y: 0, clipPath: "inset(0 0 0% 0)" }}
        transition={{ duration, delay, ease: [0.16, 1, 0.3, 1] }}
      >
        {text}
      </motion.span>
      <motion.span
        aria-hidden="true"
        className="minimalist-text-metal"
        animate={{ opacity: hovered ? 1 : 0 }}
        transition={{ duration: reduceMotion ? 0 : 0.28, ease: "easeOut" }}
      >
        {text}
      </motion.span>
    </span>
  );
}
