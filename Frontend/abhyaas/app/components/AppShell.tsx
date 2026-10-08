"use client";

import { BadgeCheck, BarChart3, BookOpen, Bot, ChevronDown, ChevronRight, FileText, GraduationCap, Home, Info, LogOut, Mail, Menu, NotebookPen, ShieldCheck, Sparkles, Swords, UserRound, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import ExamSwitcher from "./ExamSwitcher";
import { useAuth } from "./AuthProvider";
import NavigationHint from "./NavigationHint";
import DailyCheckin from "./DailyCheckin";

const desktopSections = [
  { label: "Learn", items: [
    { label: "Home", href: "/", icon: Home },
    { label: "Exam info", href: "/exam-info", icon: Info },
    { label: "Subjects", href: "/subjects", icon: GraduationCap },
  ] },
  { label: "Prepare", items: [
    { label: "Mistake notebook", href: "/mistake-notebook", icon: NotebookPen },
    { label: "Doubt solver", href: "/doubt-solver", icon: Bot },
    { label: "Previous papers", href: "/papers", icon: FileText },
    { label: "Progress", href: "/progress", icon: BarChart3 },
  ] },
  { label: "Abhyaas", items: [
    { label: "About", href: "/about", icon: BookOpen },
    { label: "Privacy", href: "/privacy", icon: ShieldCheck },
  ] },
];

const desktopItems = desktopSections.flatMap((section) => section.items);

const mobileItems = desktopItems.filter(({ label }) => ["Subjects", "Mistake notebook", "Doubt solver", "Previous papers", "Progress"].includes(label));

export default function AppShell({ active, children }: { active: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const { user, signOut } = useAuth();
  const profileRef = useRef<HTMLDivElement>(null);
  const profileTrigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!profileOpen) return;
    const outside = (event: PointerEvent) => { if (!profileRef.current?.contains(event.target as Node)) setProfileOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setProfileOpen(false); profileTrigger.current?.focus(); } };
    document.addEventListener("pointerdown", outside); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [profileOpen]);

  const initials = user?.name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <Link href="/" className="app-brand"><span><Swords size={18} /></span> ABHYAAS</Link>
        <ExamSwitcher compact />
        <div className="app-context app-user-context">
          {user ? <span className="app-user-avatar">{initials}</span> : <span className="status-dot" />}
          <span className="app-user-copy"><strong>{user?.name ?? "Study workspace"}</strong><small>{user?.email ?? "CDS preparation"}</small></span>
          {user && <button className="app-signout" type="button" onClick={() => void signOut()} aria-label="Sign out"><LogOut size={15} /></button>}
        </div>
        <button className="app-menu-toggle" type="button" onClick={() => setOpen(!open)} aria-label={open ? "Close navigation" : "Open navigation"} aria-expanded={open} aria-controls="study-sidebar">{open ? <X size={20} /> : <Menu size={20} />}</button>
      </header>
      <aside id="study-sidebar" className={`app-sidebar ${open ? "is-open" : ""}`}>
        <div className="sidebar-intro">
          <span className="sidebar-intro-mark" aria-hidden="true"><Sparkles size={16} /></span>
          <div className="sidebar-intro-copy"><strong>Study workspace</strong><small>Your CDS preparation, together</small></div>
        </div>
        <nav className="sidebar-navigation" aria-label="Study navigation">
          {desktopSections.map((section) => <section className="sidebar-nav-section" key={section.label}>
            <span className="sidebar-section-label">{section.label}</span>
            {section.items.map(({ label, href, icon: Icon }) => <Link className={active === label ? "active" : ""} aria-current={active === label ? "page" : undefined} href={href} key={label} onClick={() => setOpen(false)}>
              <span className="sidebar-nav-icon" data-nav-icon={href.slice(1) || "home"} aria-hidden="true"><Icon size={17} /></span>
              <span className="sidebar-nav-copy">{label === "Progress" ? "Daily plan & progress" : label}</span>
              <ChevronRight className="sidebar-nav-arrow" size={14} />
              <NavigationHint />
            </Link>)}
          </section>)}
        </nav>
        <div ref={profileRef} className={`sidebar-profile ${profileOpen ? "is-open" : ""}`}>
          <button ref={profileTrigger} type="button" className="sidebar-profile-trigger" onClick={() => setProfileOpen((value) => !value)} aria-expanded={profileOpen} aria-controls="sidebar-account-details">
            <span className="sidebar-profile-avatar">{initials || <UserRound size={17} />}</span>
            <span><strong>{user?.name ?? "Your profile"}</strong><small>View profile</small></span>
            <ChevronDown size={16} />
          </button>
          {profileOpen && <div className="sidebar-profile-details" id="sidebar-account-details" aria-label="Account details">
            <strong className="sidebar-account-name">{user?.name ?? "Your account"}</strong>
            <span><Mail size={14} /><span>{user?.email ?? "Sign in to see account details"}</span></span>
            {user && <span><BadgeCheck size={14} /><span>{user.is_verified ? "Verified account" : "Email verification pending"}</span></span>}
            {user && <button type="button" onClick={() => void signOut()}><LogOut size={14} /> Sign out</button>}
          </div>}
        </div>
      </aside>
      <div className="app-content">{children}</div>
      {user && <DailyCheckin />}
      <nav className="app-bottom-nav" aria-label="Application navigation">
        {mobileItems.map(({ label, href, icon: Icon }) => <Link className={active === label ? "active" : ""} aria-current={active === label ? "page" : undefined} href={href} key={label}><Icon size={19} /><span>{label === "Previous papers" ? "Papers" : label === "Doubt solver" ? "Ask AI" : label === "Mistake notebook" ? "Mistakes" : label === "Progress" ? "Today" : label}</span><NavigationHint /></Link>)}
      </nav>
    </div>
  );
}
