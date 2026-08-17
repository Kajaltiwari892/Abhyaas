"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

export default function MotionLayer({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const elements = Array.from(root.querySelectorAll<HTMLElement>(
      "main > section:not(.hero), .workspace-header, .feature-card, .subject-row, .dashboard-card, .academy-route-grid article, .subject-page-card, .paper-type-grid article, .value-grid article",
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
      entries.forEach((entry) => entry.target.classList.toggle("is-revealed", entry.isIntersecting));
    }, { threshold: 0.08, rootMargin: "-5% 0px -7% 0px" });

    elements.forEach((element) => observer.observe(element));

    let navigationTimer = 0;
    const handleNavigation = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const target = event.target as HTMLElement;
      const anchor = target.closest<HTMLAnchorElement>("a[href]");
      if (!anchor || anchor.target || anchor.hasAttribute("download")) return;
      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) return;
      const url = new URL(anchor.href, window.location.href);
      if (url.origin !== window.location.origin) return;
      if (url.pathname === window.location.pathname && url.search === window.location.search) return;
      event.preventDefault();
      root.classList.add("is-leaving");
      navigationTimer = window.setTimeout(() => router.push(`${url.pathname}${url.search}${url.hash}`), 210);
    };
    root.addEventListener("click", handleNavigation);

    return () => {
      observer.disconnect();
      root.removeEventListener("click", handleNavigation);
      window.clearTimeout(navigationTimer);
    };
  }, [pathname, router]);

  return <div ref={rootRef} key={pathname} className="route-stage">{children}</div>;
}
