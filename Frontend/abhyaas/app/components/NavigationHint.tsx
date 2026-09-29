"use client";
import { useLinkStatus } from "next/link";
export default function NavigationHint() {
  const { pending } = useLinkStatus();
  return <span className={`navigation-hint ${pending ? "is-pending" : ""}`} aria-hidden="true" />;
}
