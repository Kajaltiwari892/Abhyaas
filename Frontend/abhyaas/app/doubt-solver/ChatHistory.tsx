"use client";

import { ArrowUpRight, LoaderCircle, MessageSquare, Plus, Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { getConversations, type ConversationItem } from "@/lib/study-api";
import s from "./chat-history.module.css";

export default function ChatHistory({ token, currentId, disabled, version, open, onClose, onNew, onOpen }: {
  token: string | null; currentId?: string; disabled: boolean; version: number; open: boolean;
  onClose: () => void; onNew: () => void; onOpen: (id: string) => Promise<boolean>;
}) {
  const [items, setItems] = useState<ConversationItem[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [openingId, setOpeningId] = useState<string>();
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [search, setSearch] = useState("");
  const panelRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const cached = useRef({ token: "", version: -1, retry: -1, at: 0 });
  const closeAction = useRef(onClose);
  useEffect(() => { closeAction.current = onClose; }, [onClose]);

  useEffect(() => {
    if (!open || !token) return;
    const previous = cached.current;
    if (previous.token === token && previous.version === version && previous.retry === retry && Date.now() - previous.at < 60_000) return;
    let alive = true;
    queueMicrotask(() => { if (alive) { setLoading(true); setError(""); } });
    getConversations(token).then((data) => {
      if (!alive) return;
      setItems(data.items); setHasMore(data.has_more);
      cached.current = { token, version, retry, at: Date.now() };
    }).catch((e) => {
      if (alive) setError(e instanceof Error ? e.message : "Could not load conversations.");
    }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [open, token, version, retry]);

  useEffect(() => {
    if (!open) return;
    const mobile = window.matchMedia("(max-width:1100px)");
    const frame = requestAnimationFrame(() => { if (mobile.matches) closeRef.current?.focus({ preventScroll: true }); });
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeAction.current(); document.getElementById("chat-history-toggle")?.focus();
      }
      if (event.key !== "Tab" || !mobile.matches) return;
      const controls = Array.from(panelRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled), input:not(:disabled), a[href]") ?? []);
      const first = controls[0], last = controls.at(-1);
      if (event.shiftKey && (document.activeElement === first || !panelRef.current?.contains(document.activeElement))) {
        event.preventDefault(); last?.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !panelRef.current?.contains(document.activeElement))) {
        event.preventDefault(); first?.focus();
      }
    };
    document.addEventListener("keydown", keyboard);
    return () => { cancelAnimationFrame(frame); document.removeEventListener("keydown", keyboard); };
  }, [open]);

  const more = async () => {
    if (!token || loading) return;
    setLoading(true); setError("");
    try {
      const data = await getConversations(token, items.length);
      setItems((old) => [...old, ...data.items.filter((item) => !old.some((existing) => existing.id === item.id))]);
      setHasMore(data.has_more);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load conversations."); }
    finally { setLoading(false); }
  };
  const close = () => { onClose(); document.getElementById("chat-history-toggle")?.focus(); };
  const closeOnSmallScreen = () => { if (window.matchMedia("(max-width:1100px)").matches) close(); };
  const visibleItems = items.filter((item) => item.title.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()));

  // Keep the rail mounted for closing animation and cache. Inert prevents hidden focus.
  return <>
    <button className={s.backdrop} data-open={open} aria-label="Close chat history" tabIndex={-1} aria-hidden={!open} onClick={close} />
    <div className={s.rail} data-open={open} inert={!open} aria-hidden={!open}>
      <aside ref={panelRef} className={s.panel} id="chat-history-panel" aria-label="Saved conversations">
        <header className={s.header}>
          <div><span className={s.eyebrow}>YOUR STUDY SPACE</span><h2>Conversations</h2></div>
          <button ref={closeRef} className={s.iconButton} aria-label="Hide chat history" onClick={close}><X size={16} /></button>
        </header>
        <button className={s.newChat} disabled={disabled} onClick={() => { onNew(); closeOnSmallScreen(); }}><Plus size={17} /> New conversation <span>↗</span></button>
        <label className={s.search}><Search size={14} /><input aria-label="Search loaded conversations" placeholder="Find a conversation" value={search} onChange={(event) => setSearch(event.target.value)} />{search && <button aria-label="Clear conversation search" onClick={() => setSearch("")}><X size={13} /></button>}</label>
        <div className={s.listHeading}><span>Recent chats</span>{items.length > 0 && <span>{items.length}{hasMore ? "+" : ""}</span>}</div>
        {error && <div className={s.error} role="alert"><p>{error}</p><button onClick={() => setRetry((v) => v + 1)}>Try again</button></div>}
        <nav className={s.list} aria-label="Chat history" aria-busy={loading || !!openingId}>
          {visibleItems.map((item) => <button key={item.id} disabled={disabled || !!openingId} className={s.chat} title={item.title} aria-current={item.id === currentId ? "page" : undefined} onClick={async () => {
            setOpeningId(item.id);
            try { if (await onOpen(item.id)) closeOnSmallScreen(); }
            finally { setOpeningId(undefined); }
          }}>
            <span className={s.chatIcon}>{openingId === item.id ? <LoaderCircle size={15} className={s.spin} /> : <MessageSquare size={15} />}</span>
            <span className={s.chatCopy}><strong>{item.title}</strong><small>{new Date(item.updated_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}{item.id === currentId && " · Open now"}</small></span>
            <ArrowUpRight size={13} className={s.openArrow} />
          </button>)}
          {loading && !items.length && <div className={s.skeleton} role="status" aria-label="Loading chats"><span /><span /><span /></div>}
          {!visibleItems.length && !loading && !error && <div className={s.empty}><span><MessageSquare size={22} /></span><strong>{search ? "No matching chats" : "Room for your next idea"}</strong><p>{search ? "Try another word, or load more conversations below." : token ? "Ask a question. Your conversations will be saved here, ready to pick up later." : "Sign in to see your saved conversations."}</p></div>}
        </nav>
        {loading && !!items.length && <p className={s.status} role="status">Updating conversations…</p>}
        {hasMore && <button className={s.more} disabled={loading || disabled} onClick={() => void more()}>Load more conversations</button>}
        <p className={s.footnote}>Saved privately to your account</p>
      </aside>
    </div>
  </>;
}
