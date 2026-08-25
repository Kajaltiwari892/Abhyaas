"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const error = new URLSearchParams(window.location.search).get("google_error");
    router.replace(error ? `/login?google_error=${encodeURIComponent(error)}` : "/login");
  }, [router]);

  return <main className="auth-route-loading" aria-label="Completing Google sign in"><span /><p>Completing secure sign in…</p></main>;
}
