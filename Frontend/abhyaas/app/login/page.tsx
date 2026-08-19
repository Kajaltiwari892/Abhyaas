"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Eye, EyeOff, Swords } from "lucide-react";
import { useState, type FormEvent } from "react";
import authImage from "../../assets/img5.png";

type AuthMode = "login" | "signup";

export default function LoginPage() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [showPassword, setShowPassword] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const isLogin = mode === "login";

  function changeMode(nextMode: AuthMode) {
    setMode(nextMode);
    setSubmitted(false);
    setShowPassword(false);
  }

  function submitAuthentication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
  }

  return (
    <main className="auth-page">
      <section className="auth-form-panel">
        <div className="auth-form-shell">
          <Link className="auth-brand" href="/"><span><Swords size={19} /></span>ABHYAAS</Link>

          <div className="auth-heading">
            <span>YOUR PREPARATION SPACE</span>
            <h1>{isLogin ? "Welcome back." : "Begin your preparation."}</h1>
            <p>{isLogin ? "Continue from where you left off and keep your preparation moving." : "Create one free account for practice, papers, progress and doubt-solving."}</p>
          </div>

          <div className="auth-mode-switch" aria-label="Authentication mode">
            <button type="button" className={isLogin ? "active" : ""} onClick={() => changeMode("login")}>Sign in</button>
            <button type="button" className={!isLogin ? "active" : ""} onClick={() => changeMode("signup")}>Create account</button>
          </div>

          <form className="auth-form" onSubmit={submitAuthentication}>
            {!isLogin && <label><span>Full name</span><input name="name" type="text" autoComplete="name" placeholder="Your full name" required /></label>}
            <label><span>Email address</span><input name="email" type="email" autoComplete="email" placeholder="you@example.com" required /></label>
            <label>
              <span>Password</span>
              <span className="auth-password-field"><input name="password" type={showPassword ? "text" : "password"} autoComplete={isLogin ? "current-password" : "new-password"} placeholder={isLogin ? "Enter your password" : "Create a password"} minLength={8} required /><button type="button" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></span>
            </label>
            {!isLogin && <label><span>Confirm password</span><input name="confirm-password" type="password" autoComplete="new-password" placeholder="Repeat your password" minLength={8} required /></label>}

            {isLogin && <div className="auth-form-options"><label><input type="checkbox" name="remember" /> <span>Remember me</span></label><button type="button">Forgot password?</button></div>}

            <button className="auth-submit-static" type="submit">{isLogin ? "Sign in" : "Create free account"}<ArrowRight size={16} /></button>
            {submitted && <p className="auth-status" role="status">The interface is ready. Secure account authentication will be connected during the backend phase.</p>}
          </form>

          <p className="auth-alternate">{isLogin ? "New to Abhyaas?" : "Already have an account?"}<button type="button" onClick={() => changeMode(isLogin ? "signup" : "login")}>{isLogin ? "Create an account" : "Sign in"}</button></p>
          <Link className="auth-back" href="/"><ArrowLeft size={15} /> Return to home</Link>
        </div>
      </section>

      <aside className="auth-visual-panel">
        <Image src={authImage} alt="Indian defence officer with a message about pursuing a dream" fill priority sizes="(max-width: 900px) 100vw, 52vw" />
        <div className="auth-image-overlay" />
        {/* <div className="auth-image-copy"><span>CDS PREPARATION · FREE ACCESS</span><h2>The work is yours.<br />The path should be clear.</h2><p>One focused place to learn, practise and return stronger tomorrow.</p></div> */}
      </aside>
    </main>
  );
}
