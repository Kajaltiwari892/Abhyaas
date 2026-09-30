"use client";

import { MessageSquare, Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { getConversations, type ConversationItem } from "@/lib/study-api";
import s from "./chat-history.module.css";

export default function ChatHistory({ token, currentId, disabled, version, open, onClose, onNew, onOpen }: {
  token: string | null; currentId?: string; disabled: boolean; version: number; open: boolean;
  onClose: () => void; onNew: () => void; onOpen: (id: string) => Promise<boolean>;
}) {
  const [items, setItems] = useState<ConversationItem[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!open || !token) return;
    let alive = true;
    queueMicrotask(() => { if (alive) { setLoading(true); setError(""); } });
    getConversations(token).then((data) => { if (alive) { setItems(data.items); setHasMore(data.has_more); } })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : "Could not load conversations."); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [open, token, version, retry]);
  useEffect(() => {
    if (!open) return;
    const escape = (e: KeyboardEvent) => { if (e.key === "Escape") { onClose(); document.getElementById("chat-history-toggle")?.focus(); } };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [open, onClose]);
  const more = async () => {
    if (!token || loading) return;
    setLoading(true); setError("");
    try { const data = await getConversations(token, items.length); setItems((old) => [...old, ...data.items.filter((item) => !old.some((existing) => existing.id === item.id))]); setHasMore(data.has_more); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load conversations."); } finally { setLoading(false); }
  };
  const closeOnSmallScreen = () => { if (window.matchMedia("(max-width:1100px)").matches) onClose(); };
  if (!open) return null;
  return <aside className={s.panel} id="chat-history-panel" aria-label="Saved conversations">
    <header><strong>Your chats</strong><button aria-label="Hide chat history" onClick={() => { onClose(); document.getElementById("chat-history-toggle")?.focus(); }}><X size={15} /></button></header>
    <button className={s.newChat} disabled={disabled} onClick={() => { onNew(); closeOnSmallScreen(); }}><Plus size={15} /> New conversation</button>
    {error && <p role="alert">{error} <button onClick={() => setRetry((v) => v+1)}>Retry</button></p>}
    <nav className={s.list} aria-label="Chat history">{items.map((item) => <button key={item.id} disabled={disabled} aria-current={item.id === currentId ? "page" : undefined} onClick={async () => { if (await onOpen(item.id)) closeOnSmallScreen(); }}><MessageSquare size={14} /><span><strong>{item.title}</strong><small>{new Date(item.updated_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}</small></span></button>)}</nav>
    {!items.length && !loading && !error && <p>{token ? "Your saved conversations will appear here." : "Sign in to view your conversations."}</p>}
    {loading && <p role="status">Loading chats…</p>}
    {hasMore && <button className={s.more} disabled={loading || disabled} onClick={() => void more()}>Load more</button>}
  </aside>;
}
