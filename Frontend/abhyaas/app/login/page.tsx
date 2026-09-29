"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Eye, EyeOff, Swords } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";
import authImage from "../../assets/img5.png";
import {
  ApiError,
  getGoogleSignInUrl,
  loginAccount,
  registerAccount,
  requestPasswordReset,
  resetPassword,
  verifyEmail,
} from "@/lib/auth-api";
import { useAuth } from "../components/AuthProvider";

type AuthMode = "login" | "signup" | "forgot" | "reset";
type FormStatus = { kind: "success" | "error" | "info"; message: string } | null;
type AuthNotice = { title: string; message: string; action?: "login" } | null;

const googleErrorNotices: Record<string, Exclude<AuthNotice, null>> = {
  not_configured: {
    title: "Google sign-in is unavailable",
    message: "Google authentication is not configured for this environment yet.",
  },
  cancelled: {
    title: "Google sign-in was cancelled",
    message: "The secure sign-in session was not completed. Please start it again.",
  },
  invalid_state: {
    title: "Google sign-in session expired",
    message: "The browser could not verify the sign-in session. Please start it again in this tab.",
  },
  failed: {
    title: "Google could not verify the account",
    message: "Google returned an invalid or incomplete identity response. Please try once more.",
  },
  account_conflict: {
    title: "This email is linked differently",
    message: "Sign in with your existing method first before connecting this Google account.",
  },
};

const headings: Record<AuthMode, { eyebrow: string; title: string; description: string }> = {
  login: {
    eyebrow: "YOUR PREPARATION SPACE",
    title: "Welcome back.",
    description: "Continue from where you left off and keep your preparation moving.",
  },
  signup: {
    eyebrow: "FREE CDS PREPARATION",
    title: "Begin your preparation.",
    description: "Create one free account for practice, papers, progress and doubt-solving.",
  },
  forgot: {
    eyebrow: "ACCOUNT RECOVERY",
    title: "Reset your password.",
    description: "Enter your email and we will create a secure password-reset link.",
  },
  reset: {
    eyebrow: "SECURE YOUR ACCOUNT",
    title: "Choose a new password.",
    description: "Use at least eight characters with a letter and a number.",
  },
};

function getFormValue(form: FormData, name: string) {
  return String(form.get(name) ?? "").trim();
}

export default function LoginPage() {
  const router = useRouter();
  const { completeAuthentication } = useAuth();
  const verificationStarted = useRef(false);
  const [mode, setMode] = useState<AuthMode>("login");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [pending, setPending] = useState(false);
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<FormStatus>(null);
  const [notice, setNotice] = useState<AuthNotice>(null);
  const [resetToken, setResetToken] = useState("");
  const isLogin = mode === "login";
  const isSignup = mode === "signup";
  const heading = headings[mode];

  useEffect(() => {
    if (!notice) return;
    const options = {
      description: notice.message,
      id: "auth-notice",
      action: notice.action === "login" ? { label: "Go to sign in", onClick: () => changeMode("login") } : undefined,
    };
    if (notice.title === "Check your email") toast.success(notice.title, options);
    else toast.error(notice.title, options);
  }, [notice]);

  useEffect(() => {
    if (!status) return;
    if (status.kind === "success") toast.success(status.message, { id: "auth-status" });
    else if (status.kind === "error") toast.error(status.message, { id: "auth-status" });
    else toast.loading(status.message, { id: "auth-status" });
  }, [status]);

  useEffect(() => {
    if (verificationStarted.current) return;
    verificationStarted.current = true;
    const parameters = new URLSearchParams(window.location.search);
    const verificationToken = parameters.get("verify");
    const passwordResetToken = parameters.get("reset");
    const googleError = parameters.get("google_error");

    if (googleError) {
      queueMicrotask(() => setNotice(googleErrorNotices[googleError] ?? {
        title: "Google sign-in was not completed",
        message: `Please try Google again. Error reference: ${googleError}`,
      }));
      window.history.replaceState(null, "", "/login");
      return;
    }

    if (passwordResetToken) {
      queueMicrotask(() => {
        setResetToken(passwordResetToken);
        setMode("reset");
      });
      return;
    }
    if (!verificationToken) return;

    queueMicrotask(() => {
      setPending(true);
      setStatus({ kind: "info", message: "Verifying your email address…" });
    });
    verifyEmail(verificationToken)
      .then(() => {
        setMode("login");
        setStatus({ kind: "success", message: "Your email is verified. You can sign in now." });
        window.history.replaceState(null, "", "/login");
      })
      .catch(() => {
        setStatus({ kind: "error", message: "This verification link is invalid or has expired." });
      })
      .finally(() => setPending(false));
  }, []);

  function changeMode(nextMode: AuthMode) {
    setMode(nextMode);
    setStatus(null);
    setNotice(null);
    setShowPassword(false);
    setShowConfirmPassword(false);
  }

  function showResetEmailConfirmation() {
    setStatus(null);
    setNotice({
      title: "Check your email",
      message: "Your password-reset link is on its way. It may take a minute, and please check your Spam folder too.",
    });
  }

  async function handleForgotPasswordClick() {
    changeMode("forgot");

    const requestedEmail = email.trim();
    if (!isValidEmail(requestedEmail)) {
      setNotice({
        title: "Enter your email address",
        message: "Tell us which email you use for Abhyaas, then we’ll send your secure reset link.",
      });
      return;
    }

    setPending(true);
    try {
      await requestPasswordReset(requestedEmail);
      showResetEmailConfirmation();
    } catch {
      setNotice({ title: "We couldn’t send the email yet", message: getFailureMessage("forgot") });
    } finally {
      setPending(false);
    }
  }

  async function submitAuthentication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = getFormValue(form, "email");
    const password = getFormValue(form, "password");
    const confirmPassword = getFormValue(form, "confirm-password");

    if ((isSignup || mode === "reset") && password !== confirmPassword) {
      setNotice({ title: "Passwords do not match", message: "Please enter the same password in both fields." });
      return;
    }

    setPending(true);
    setStatus(null);
    try {
      if (isSignup) {
        const session = await registerAccount({
          name: getFormValue(form, "name"),
          email,
          password,
        });
        completeAuthentication(session);
        router.replace("/progress");
        return;
      }

      if (mode === "forgot") {
        await requestPasswordReset(email);
        showResetEmailConfirmation();
        return;
      }

      if (mode === "reset") {
        if (!resetToken) throw new ApiError("The password-reset link is missing.", 400);
        await resetPassword(resetToken, password);
        setMode("login");
        setResetToken("");
        setStatus({ kind: "success", message: "Your password has been updated. You can sign in now." });
        window.history.replaceState(null, "", "/login");
        return;
      }

      const session = await loginAccount({
        email,
        password,
      });
      completeAuthentication(session);
      router.replace(getSafeDestination());
    } catch (error: unknown) {
      if (isSignup && error instanceof ApiError && error.status === 409) {
        setNotice({
          title: "You already have an account",
          message: "This email is already connected to Abhyaas. Please sign in to continue your preparation.",
          action: "login",
        });
      } else {
        setNotice({ title: "Something needs attention", message: getFailureMessage(mode) });
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-form-panel">
        <div className="auth-form-shell">
          <Link className="auth-brand" href="/"><span><Swords size={19} /></span>ABHYAAS</Link>

          <div className="auth-heading">
            <span>{heading.eyebrow}</span>
            <h1>{heading.title}</h1>
            <p>{heading.description}</p>
          </div>

          <div className="auth-mode-switch" aria-label="Authentication mode">
            <button type="button" className={isLogin ? "active" : ""} onClick={() => changeMode("login")}>Sign in</button>
            <button type="button" className={isSignup ? "active" : ""} onClick={() => changeMode("signup")}>Create account</button>
          </div>

          <form className="auth-form" onSubmit={submitAuthentication}>
            {isSignup && <label><span>Full name</span><input name="name" type="text" autoComplete="name" placeholder="Your full name" minLength={2} required /></label>}
            {(isLogin || isSignup || mode === "forgot") && <label><span>Email address</span><input name="email" type="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>}
            {mode !== "forgot" && <label>
              <span>{mode === "reset" ? "New password" : "Password"}</span>
              <span className="auth-password-field"><input name="password" type={showPassword ? "text" : "password"} autoComplete={isLogin ? "current-password" : "new-password"} placeholder={isLogin ? "Enter your password" : "Create a password"} minLength={8} required /><button type="button" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <Eye size={17} /> : <EyeOff size={17} />}</button></span>
            </label>}
            {(isSignup || mode === "reset") && <label><span>Confirm password</span><span className="auth-password-field"><input name="confirm-password" type={showConfirmPassword ? "text" : "password"} autoComplete="new-password" placeholder="Repeat your password" minLength={8} required /><button type="button" onClick={() => setShowConfirmPassword((visible) => !visible)} aria-label={showConfirmPassword ? "Hide confirmed password" : "Show confirmed password"}>{showConfirmPassword ? <Eye size={17} /> : <EyeOff size={17} />}</button></span></label>}

            {isLogin && <div className="auth-form-options auth-forgot-only"><button type="button" onClick={handleForgotPasswordClick} disabled={pending}>Forgot password?</button></div>}

            <button className="auth-submit-static" type="submit" disabled={pending}>
              {pending ? "Please wait…" : getSubmitLabel(mode)}{!pending && <ArrowRight size={16} />}
            </button>
            {(isLogin || isSignup) && <><div className="auth-divider"><span>or continue with</span></div><button className="auth-google" type="button" onClick={() => window.location.assign(getGoogleSignInUrl())}><span aria-hidden="true">G</span>Sign in with Google</button></>}
          </form>

          <p className="auth-alternate">
            {isLogin ? "New to Abhyaas?" : "Already have an account?"}
            <button type="button" onClick={() => changeMode(isLogin ? "signup" : "login")}>{isLogin ? "Create an account" : "Sign in"}</button>
          </p>
          <p className="auth-privacy-note">By continuing, you acknowledge the <Link href="/privacy">Privacy policy</Link>.</p>
        </div>
      </section>

      <aside className="auth-visual-panel">
        <Image src={authImage} alt="Indian defence officer with a message about pursuing a dream" fill priority sizes="(max-width: 900px) 100vw, 52vw" />
        <div className="auth-image-overlay" />
      </aside>
    </main>
  );
}

function getSubmitLabel(mode: AuthMode) {
  if (mode === "signup") return "Create free account";
  if (mode === "forgot") return "Send reset email";
  if (mode === "reset") return "Update password";
  return "Sign in";
}

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function getSafeDestination() {
  const next = new URLSearchParams(window.location.search).get("next");
  return next?.startsWith("/") && !next.startsWith("//") ? next : "/progress";
}

function getFailureMessage(mode: AuthMode) {
  if (mode === "signup") return "Your account is almost ready, but we could not finish signing you in. Please try once more.";
  if (mode === "forgot") return "That reset request did not go through. Please wait a moment and try again.";
  if (mode === "reset") return "That password change did not go through. Please request a fresh reset link.";
  return "Those details did not match an account. Please check your email and password.";
}
