"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { googleCallbackRedirect } from "@/lib/auth-routing";
import { useAuth } from "../../components/AuthProvider";

export default function AuthCallbackPage() {
  const router = useRouter();
  const { status } = useAuth();

  useEffect(() => {
    router.prefetch("/progress");
  }, [router]);

  useEffect(() => {
    const error = new URLSearchParams(window.location.search).get("google_error");
    const destination = googleCallbackRedirect(status, error);
    if (destination) router.replace(destination);
  }, [router, status]);

  return <main className="auth-route-loading" role="status" aria-live="polite"><span aria-hidden="true" /><p>{status === "authenticated" ? "Opening your progress…" : "Completing secure sign in…"}</p></main>;
}
