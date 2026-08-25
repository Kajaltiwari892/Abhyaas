"use client";

import { Check, ChevronDown, LockKeyhole, Shield } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const upcomingExams = [
  { name: "NEET", description: "Medical entrance" },
  { name: "JEE", description: "Engineering entrance" },
  { name: "UPSC CSE", description: "Civil services" },
];

export default function ExamSwitcher({ compact = false }: { compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const switcherRef = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    if (!open) return;

    function closeFromOutside(event: PointerEvent) {
      if (!switcherRef.current?.contains(event.target as Node)) setOpen(false);
    }

    function closeFromEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("pointerdown", closeFromOutside);
    document.addEventListener("keydown", closeFromEscape);
    return () => {
      document.removeEventListener("pointerdown", closeFromOutside);
      document.removeEventListener("keydown", closeFromEscape);
    };
  }, [open]);

  return (
    <details ref={switcherRef} open={open} onToggle={(event) => setOpen(event.currentTarget.open)} className={`exam-switcher ${compact ? "compact" : ""}`}>
      <summary aria-label="Choose an exam">
        <span className="exam-shield"><Shield size={14} /></span>
        <span className="exam-current"><small>Preparing for</small><strong>CDS</strong></span>
        <ChevronDown className="exam-chevron" size={15} />
      </summary>
      <div className="exam-menu">
        <span className="exam-menu-label">Choose your exam</span>
        <div className="exam-option selected">
          <span className="exam-option-icon"><Shield size={16} /></span>
          <span><strong>CDS</strong><small>Defence services</small></span>
          <Check size={15} />
        </div>
        {upcomingExams.map((exam) => (
          <div className="exam-option disabled" key={exam.name} aria-disabled="true">
            <span className="exam-option-icon"><LockKeyhole size={14} /></span>
            <span><strong>{exam.name}</strong><small>{exam.description}</small></span>
            <em>Coming soon</em>
          </div>
        ))}
        <p>Abhyaas is currently focused entirely on CDS preparation.</p>
      </div>
    </details>
  );
}
