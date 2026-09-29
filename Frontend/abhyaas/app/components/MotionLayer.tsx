"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

export default function MotionLayer({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    // Workspace navigation must stay immediate. Decorative scroll reveals are for
    // the public landing page only, never hide already-rendered study content.
    if (!root || pathname !== "/") return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const elements = Array.from(root.querySelectorAll<HTMLElement>(
      ".workspace-header, .section-heading, .prep-value-grid > *, .feature-card, .dark-section-inner > *, .subject-row, .exam-card, .selection-path, .progress-copy, .progress-preview, .cds-chart-card, .closing-content, .dashboard-card, .academy-route-grid article, .subject-page-card, .paper-type-grid article, .value-grid article",
    ));

    if (reducedMotion) {
      elements.forEach((element) => element.classList.add("is-revealed"));
      return;
    }

    elements.forEach((element, index) => {
      element.classList.add("scroll-reveal");
      element.style.setProperty("--reveal-delay", `${(index % 4) * 55}ms`);
    });

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => { if (entry.isIntersecting) { entry.target.classList.add("is-revealed"); observer.unobserve(entry.target); } });
    }, { threshold: 0.08, rootMargin: "-5% 0px -7% 0px" });

    elements.forEach((element) => observer.observe(element));

    const glowPanels = Array.from(root.querySelectorAll<HTMLElement>(".prep-stack"));
    const glowObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => entry.target.classList.toggle("is-glowing", entry.isIntersecting));
    }, { threshold: 0.03, rootMargin: "-2% 0px -8% 0px" });
    glowPanels.forEach((panel) => glowObserver.observe(panel));

    return () => {
      observer.disconnect();
      glowObserver.disconnect();
    };
  }, [pathname]);

  return <div ref={rootRef} className="route-stage">{children}</div>;
}
