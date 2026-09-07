"use client";

import { ArrowLeft, Mail, Moon, ShieldCheck, Sun, Swords } from "lucide-react";
import Link from "next/link";
import { useTheme } from "../components/ThemeProvider";

const sections = [
  {
    title: "Information Abhyaas collects",
    content: (
      <>
        <p>When you create an account, Abhyaas stores your name, email address, account status and account creation time. Passwords are never stored as readable text; only an Argon2 password hash is retained.</p>
        <p>If you choose Google sign-in, Abhyaas receives your verified email address, name and Google account identifier. We do not receive your Google password or request access to Gmail, Drive, Calendar, contacts or other Google services.</p>
        <p>For account security, we process session records, token hashes, sign-in timestamps and privacy-preserving digests associated with failed sign-in attempts. Standard server logs may also contain an IP address, requested page and technical error information.</p>
        <p>When saved practice and progress features are enabled, Abhyaas may store your answers, scores, attempted subjects, study time and practice history so those features work for you.</p>
      </>
    ),
  },
  {
    title: "How information is used",
    content: <p>We use this information to create and secure your account, keep you signed in, restore your preparation space, provide practice and progress features, prevent abuse, diagnose technical problems, respond to support requests and improve the platform.</p>,
  },
  {
    title: "Google user data",
    content: <p>Google profile information is used only to identify you, create or connect your Abhyaas account and display your account details. Google user data is not used for advertising, sold, or shared for unrelated purposes. Abhyaas does not store Google access or refresh tokens.</p>,
  },
  {
    title: "Cookies and sessions",
    content: <p>Abhyaas uses a strictly necessary HttpOnly authentication cookie. It cannot be read by normal frontend JavaScript and is used to restore and rotate your secure session. We do not currently use advertising or behavioural-tracking cookies.</p>,
  },
  {
    title: "When information is shared",
    content: <p>We do not sell personal information. Information may be processed by infrastructure or authentication providers required to operate Abhyaas, including Google when you voluntarily choose Google sign-in. Information may also be disclosed when required by law, to protect users, or to investigate misuse. Providers are limited to the information needed for their service.</p>,
  },
  {
    title: "Retention and deletion",
    content: <p>Account information is retained while your account remains active or while it is reasonably needed to provide the service, meet legal obligations, resolve disputes and protect the platform. Short-lived authentication and password-reset credentials expire automatically. You may request account deletion using the contact address below.</p>,
  },
  {
    title: "Your choices and rights",
    content: <p>You may ask to access, correct or delete your personal information, withdraw consent where processing relies on consent, or raise a privacy grievance. We may need to verify your identity before completing a request. You can also revoke Abhyaas access from your Google Account permissions.</p>,
  },
  {
    title: "Security",
    content: <p>Abhyaas uses password hashing, short-lived access credentials, rotating hashed sessions, HttpOnly cookies, origin checks, login throttling and server-side authorization. No internet service can promise absolute security, but we limit the information collected and apply safeguards appropriate to the current platform.</p>,
  },
  {
    title: "Children",
    content: <p>Abhyaas is designed for CDS aspirants and is not intended for children under 18. We do not knowingly create accounts for children. If you believe a child has provided personal information, contact us so it can be reviewed and removed.</p>,
  },
  {
    title: "Changes to this policy",
    content: <p>This policy may be updated when Abhyaas adds features, changes providers or needs to reflect legal requirements. The effective date will be updated, and material changes will be communicated within the platform where appropriate.</p>,
  },
];

export default function PrivacyPage() {
  const { theme, toggleTheme } = useTheme();

  return (
    <main className="privacy-page">
      <header className="privacy-nav">
        <Link href="/" className="app-brand"><span><Swords size={18} /></span> ABHYAAS</Link>
        <div className="privacy-actions"><button type="button" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>{theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}</button><Link href="/" className="privacy-back"><ArrowLeft size={15} /> Back to home</Link></div>
      </header>

      <article className="privacy-document">
        <header className="privacy-hero">
          <span><ShieldCheck size={15} /> Privacy at Abhyaas</span>
          <h1>Privacy policy</h1>
          <p>This policy explains what information Abhyaas handles, why it is needed, and the choices available to you.</p>
          <small>Effective: 25 August 2026</small>
        </header>

        <div className="privacy-summary">
          <strong>The short version</strong>
          <p>We collect only what is needed to run and secure your preparation account. We do not sell your personal information, run behavioural advertising, or ask Google for access beyond basic identity details.</p>
        </div>

        <div className="privacy-sections">
          {sections.map((section, index) => <section key={section.title}><span>{String(index + 1).padStart(2, "0")}</span><div><h2>{section.title}</h2>{section.content}</div></section>)}
        </div>

        <section className="privacy-contact">
          <span>Privacy questions or requests</span>
          <h2>Contact Abhyaas</h2>
          <p>For access, correction, deletion or grievance requests, write from the email connected to your account.</p>
          <a href="mailto:kanjal55567@gmail.com"><Mail size={16} /> kanjal55567@gmail.com</a>
        </section>
      </article>
    </main>
  );
}
