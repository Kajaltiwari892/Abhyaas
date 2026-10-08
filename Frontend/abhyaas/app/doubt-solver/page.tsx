"use client";

import { ArrowUp, ArrowUpRight, BookOpen, BrainCircuit, Check, ChevronDown, Clock3, CloudSun, ExternalLink, LoaderCircle, Plus, RotateCcw, Scale, Sparkles, X } from "lucide-react";
import { type ClipboardEvent, type FormEvent, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ApiError } from "@/lib/auth-api";
import { askDoubt, clearStudyProfile, getStudyProfile, getConversation, updateStudyProfile, type DoubtSource, type StudyProfile, type PyqResult, type PaperSolutionResult, type PracticeResult } from "@/lib/study-api";
import AppShell from "../components/AppShell";
import { useAuth } from "../components/AuthProvider";
import StudyCompanion, { CompanionMark } from "../components/StudyCompanion";
import s from "./doubt-solver.module.css";
import PyqResults from "./PyqResults";
import PaperSolutions from "./PaperSolutions";
import PracticeResults from "./PracticeResults";
import RequestStatus from "./RequestStatus";
import ChatHistory from "./ChatHistory";

const starterPrompts = ["Explain Fundamental Rights simply", "How do I solve time and work questions?", "What is the difference between weather and climate?"];
const encouragements = ["One clear concept. One step closer.", "Big ambitions start with small questions.", "Your next breakthrough starts here.", "A little curiosity goes a long way."];
const promptIcons = [Scale, Clock3, CloudSun];
type SubjectFilter = "all" | "general-knowledge" | "elementary-mathematics" | "english";
type ChatMessage = {
  id: string; role: "user" | "assistant"; content: string;
  sources?: DoubtSource[]; grounded?: boolean; followUps?: string[];
  error?: boolean; retryQuestion?: string; retryPaperId?: string;
  pyqResult?: PyqResult | PaperSolutionResult | null; practiceResult?: PracticeResult | null; answerKind?: string;
};

function AnswerContent({ content }: { content: string }) {
  const inline = (text: string) => text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, index) =>
    part.startsWith("**") ? <strong key={index}>{part.slice(2, -2)}</strong>
      : part.startsWith("`") ? <code key={index}>{part.slice(1, -1)}</code> : part);
  return <div className={s.answer}>{content.split("\n").map((line, index) => {
    const text = line.trim();
    if (!text) return <span className={s.answerSpace} key={index} />;
    if (/^---+$/.test(text)) return <hr key={index} />;
    if (/^#{1,3}\s+/.test(text)) return <h3 key={index}>{inline(text.replace(/^#{1,3}\s+/, ""))}</h3>;
    return /^[*-]\s+/.test(text)
      ? <div className={s.answerBullet} key={index}>{inline(text.replace(/^[*-]\s+/, ""))}</div>
      : <p key={index}>{inline(text.replace(/^#{1,3}\s+/, ""))}</p>;
  })}</div>;
}

export default function DoubtSolverPage() {
  const { user } = useAuth();
  return <DoubtSolverWorkspace key={user?.id ?? "guest"} />;
}

function DoubtSolverWorkspace() {
  const { accessToken, user } = useAuth();
  const firstName = user?.name.trim().split(/\s+/)[0] ?? "";
  const [question, setQuestion] = useState("");
  const [subject, setSubject] = useState<SubjectFilter>("all");
  const [conversationId, setConversationId] = useState<string>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyVersion, setHistoryVersion] = useState(0);
  const [historyOpen, setHistoryOpen] = useState(false);
  useEffect(() => { queueMicrotask(() => setHistoryOpen(window.matchMedia("(min-width:1101px)").matches)); }, []);
  const [hour, setHour] = useState<number | null>(null);
  const [messageIndex, setMessageIndex] = useState(0);
  const [profile, setProfile] = useState<StudyProfile>();
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [memoryBusy, setMemoryBusy] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [resetConfirm, setResetConfirm] = useState(false);
  const feedRef = useRef<HTMLDivElement>(null);
  const lastAnswerRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const inFlight = useRef(false);
  const memoryRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const prompt = params.get("question");
    const selected = params.get("subject");
    if (!prompt) return;
    queueMicrotask(() => {
      setQuestion(prompt.slice(0, 2000));
      if (["english", "general-knowledge", "elementary-mathematics"].includes(selected ?? "")) setSubject(selected as SubjectFilter);
      inputRef.current?.focus();
    });
  }, []);

  useEffect(() => {
    const update = () => setHour(new Date().getHours());
    queueMicrotask(update);
    const timer = window.setInterval(update, 60_000);
    const rotation = window.setInterval(() => setMessageIndex((index) => (index + 1) % encouragements.length), 8000);
    return () => { window.clearInterval(timer); window.clearInterval(rotation); };
  }, []);

  useEffect(() => {
    if (!accessToken) return;
    let active = true;
    getStudyProfile(accessToken).then((data) => { if (active) { setProfile(data); setProfileError(""); } })
      .catch(() => { if (active) setProfileError("Study memory could not load. Reopen the page to retry."); });
    return () => { active = false; };
  }, [accessToken]);

  useEffect(() => {
    const feed = feedRef.current;
    if (!feed) return;
    const answer = !loading ? lastAnswerRef.current : null;
    const top = answer ? feed.scrollTop + answer.getBoundingClientRect().top - feed.getBoundingClientRect().top - 12 : feed.scrollHeight;
    feed.scrollTo({top, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
  }, [loading, messages]);

  useEffect(() => {
    if (!memoryOpen) return;
    const outside = (event: PointerEvent) => { if (!memoryRef.current?.contains(event.target as Node)) { setMemoryOpen(false); setResetConfirm(false); } };
    const escape = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") setMemoryOpen(false); };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [memoryOpen]);

  const changeMemory = async (input: Partial<Pick<StudyProfile, "enabled" | "explanation_style">> | "clear") => {
    if (!accessToken || memoryBusy) return;
    setMemoryBusy(true);
    try {
      const data = input === "clear" ? await clearStudyProfile(accessToken) : await updateStudyProfile(accessToken, input);
      setProfile(data); setResetConfirm(false); setProfileError("");
      if (input === "clear") toast.success("Study memory cleared");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not update study memory."); }
    finally { setMemoryBusy(false); }
  };

  const pasteQuestion = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    if (!event.clipboardData.files.length) return;
    // Keep ordinary text paste available, including text copied alongside a file.
    if (event.clipboardData.getData("text/plain")) return;
    event.preventDefault();
    toast.info("Image and file uploads are paused. Please type or paste your question text.");
  };

  const submitQuestion = async (nextQuestion: string, paperQuestionId?: string) => {
    const trimmed = nextQuestion.trim();
    if (!trimmed || inFlight.current) return;
    if (!accessToken) { toast.info("Your session is loading. Please try again in a moment."); return; }
    if (trimmed && trimmed.length < 3) { toast.info("Add a little more detail to your question."); return; }
    inFlight.current = true; setLoading(true);
    const asked = trimmed;
    setQuestion("");
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: asked }]);
    try {
      const result = await askDoubt(accessToken, {
        question: asked, subject: subject === "all" ? undefined : subject, conversation_id: conversationId,
        paper_question_id: paperQuestionId,
      });
      setConversationId(result.conversation_id);
      setHistoryVersion((v) => v + 1);
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: result.answer, sources: result.sources, grounded: result.grounded, followUps: result.follow_up_questions, pyqResult: result.pyq_result, practiceResult: result.practice_result, answerKind: result.answer_kind }]);
      getStudyProfile(accessToken).then(setProfile).catch(() => {});
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "The answer could not be prepared. Please try again.";
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: message, error: true, retryQuestion: asked, retryPaperId: paperQuestionId }]);
      setQuestion(trimmed);
    } finally { inFlight.current = false; setLoading(false); }
  };

  const startNew = () => {
    if (inFlight.current) return;
    setMessages([]); setConversationId(undefined); setQuestion("");
    inputRef.current?.focus();
  };
  const openConversation = async (id: string) => {
    if (!accessToken || inFlight.current) return false;
    if (question.trim() && !window.confirm("Open this saved chat? Your unsent draft will be cleared.")) return false;
    inFlight.current = true; setHistoryLoading(true);
    try {
      const data = await getConversation(accessToken, id);
      setConversationId(data.id);
      setMessages(data.messages.map((item) => ({ id: item.id, role: item.role, content: item.content,
        sources: item.citations, grounded: item.citations.length > 0, pyqResult: item.pyq_result,
        practiceResult: item.practice_result, answerKind: item.practice_result?.kind ?? item.pyq_result?.kind ?? "explanation" })));
      setQuestion("");
      return true;
    } catch (e) { toast.error(e instanceof Error ? e.message : "Could not open this conversation."); return false; }
    finally { inFlight.current = false; setHistoryLoading(false); }
  };
  const submit = (event: FormEvent) => { event.preventDefault(); void submitQuestion(question); };
  const greeting = hour === null ? "Welcome back" : hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const prompts = profile?.suggested_questions.length === 3 ? profile.suggested_questions : starterPrompts;
  const hasMessages = messages.length > 0;

  return <AppShell active="Doubt solver">
    <div className={s.chatLayout}>
    <ChatHistory token={accessToken} currentId={conversationId} disabled={loading || historyLoading} version={historyVersion} open={historyOpen} onClose={() => setHistoryOpen(false)} onNew={startNew} onOpen={openConversation} />
    <main className={[s.workspace, hasMessages ? s.conversation : s.empty].join(" ")}>
      <header className={s.topbar}>
        <span className={s.pageLabel}><Sparkles size={15} /> Doubt solver</span>
        <div className={s.topActions}>
          <button id="chat-history-toggle" type="button" aria-expanded={historyOpen} aria-controls="chat-history-panel" onClick={() => setHistoryOpen((v) => !v)}>Chats</button>
          {hasMessages && <button type="button" onClick={startNew} disabled={loading || historyLoading} title="New conversation"><Plus size={15} /> New chat</button>}
          <div className={s.memoryAnchor} ref={memoryRef}>
            <button type="button" className={memoryOpen ? s.selected : ""} aria-expanded={memoryOpen} aria-controls="study-memory" onClick={() => setMemoryOpen((open) => !open)}><BrainCircuit size={15} /> Study memory{profile?.enabled && <i />}</button>
            {memoryOpen && <section className={s.memoryPanel} id="study-memory" aria-label="Study memory settings">
              <div className={s.memoryTitle}><strong>A tutor that knows your prep</strong><button type="button" aria-label="Close study memory" onClick={() => setMemoryOpen(false)}><X size={16} /></button></div>
              <p>Remembers study topics and your explanation style for future chats. Your memory is private to your account.</p>
              {profileError && <p role="status" className={s.fieldError}>{profileError}</p>}
              <label className={s.memoryToggle}><span>Remember my learning</span><input type="checkbox" checked={profile?.enabled ?? false} disabled={!profile || memoryBusy} onChange={(event) => void changeMemory({ enabled: event.target.checked })} /></label>
              <label className={s.styleLabel}>How should I explain?<select value={profile?.explanation_style ?? "step-by-step"} disabled={!profile || memoryBusy || !profile.enabled} onChange={(event) => void changeMemory({ explanation_style: event.target.value as StudyProfile["explanation_style"] })}><option value="step-by-step">Step by step</option><option value="concise">Keep it concise</option><option value="hints-first">Hints first</option></select></label>
              <div className={s.memoryTopics}>{profile?.topics.length ? profile.topics.map((topic) => <span key={topic.name}>{topic.name}<small>{topic.count}</small></span>) : <p>Your study topics will appear as you ask questions.</p>}</div>
              <small className={s.memoryNote}>You can pause or clear study memory anytime. Your saved chats stay available.</small>
              {resetConfirm ? <div className={s.resetConfirm}><p>Clear your topics and explanation preference? Existing chats stay saved.</p><button disabled={memoryBusy} onClick={() => void changeMemory("clear")}>Clear memory</button><button disabled={memoryBusy} onClick={() => setResetConfirm(false)}>Cancel</button></div> : <button className={s.resetMemory} disabled={!profile || memoryBusy || loading} onClick={() => setResetConfirm(true)}><RotateCcw size={12} /> Clear study memory</button>}
            </section>}
          </div>
        </div>
      </header>
      {historyLoading && <p role="status" className={s.memoryNote}>Opening saved conversation…</p>}
      <div className={s.stage}>
        {!hasMessages ? <div className={s.greeting}>
          <StudyCompanion name={firstName} />
          <h1>{greeting}{firstName ? ", " : "."}<span>{firstName && `${firstName}.`}</span></h1>
          <p key={messageIndex} className={s.encouragement}>{encouragements[messageIndex]}</p>
        </div> : <div className={s.feed} ref={feedRef} role="log" aria-label="Doubt conversation" aria-live="polite" aria-busy={loading}>
          {messages.map((message) => <article key={message.id} ref={message.role === "assistant" && message.id === messages.at(-1)?.id ? lastAnswerRef : undefined} className={[s.message, message.role === "user" ? s.userMessage : ""].join(" ")}>
            {message.role === "assistant" && <span className={s.botAvatar}><CompanionMark /></span>}
            <div className={s.messageContent}>
              <div className={s.messageHeading}>
                <span className={s.messageAuthor}>{message.role === "user" ? "You" : "Abhyaas"}</span>
                {message.pyqResult && message.pyqResult.kind !== "clarification" && <span className={s.answerKind}><BookOpen size={11} /> {message.pyqResult.kind === "paper_solution" ? "Paper solutions · answer status shown per question" : message.pyqResult.kind === "archive_info" ? "Archive coverage · based on your last search" : "From the paper archive · not AI-generated"}</span>}
                {message.role === "assistant" && !message.error && !message.pyqResult && <span className={s.answerKind}>{message.answerKind === "practice" ? <><Sparkles size={11} /> Generated practice · not actual PYQs</> : message.answerKind === "clarification" ? "Choose a topic to continue" : message.grounded ? <><Check size={11} /> Sources included</> : <><Sparkles size={11} /> AI explanation · verify important facts</>}</span>}
              </div>
              {message.error ? <div className={s.errorAnswer}><p>{message.content}</p><button disabled={loading} onClick={() => { if(message.retryPaperId){void submitQuestion(message.retryQuestion ?? "Explain this question",message.retryPaperId);}else{setQuestion(message.retryQuestion ?? ""); inputRef.current?.focus();} }}><RotateCcw size={13} /> {message.retryPaperId ? "Retry explanation" : "Edit & retry"}</button></div> : <AnswerContent content={message.content} />}
              {message.pyqResult?.kind === "paper_solution" ? <PaperSolutions result={message.pyqResult}
                current={message.id === messages.at(-1)?.id} disabled={loading || historyLoading || !!question.trim()}
                onContinue={() => void submitQuestion("Continue solving")} />
                : message.pyqResult && <PyqResults result={message.pyqResult} loading={loading} onExplain={(id, label) => void submitQuestion(label, id)} />}
              {message.practiceResult && <PracticeResults result={message.practiceResult} />}
              {!!message.sources?.length && <details className={s.sources}><summary><BookOpen size={13} /> {message.sources.length} {message.sources.length === 1 ? "source" : "sources"}<ChevronDown size={13} /></summary><div>{message.sources.map((source) => <article key={source.id}><small>{source.id} · {source.publisher}</small><strong>{source.title}</strong><p>{source.excerpt}</p>{source.source_url && <a href={source.source_url} target="_blank" rel="noreferrer">Open source <ExternalLink size={11} /></a>}</article>)}</div></details>}
              {message.pyqResult?.kind !== "paper_solution" && !!message.followUps?.length && <div className={s.followups}>{message.followUps.map((text) => <button key={text} disabled={loading} onClick={() => { setQuestion(text); inputRef.current?.focus(); }}>{text}<ArrowUpRight size={12} /></button>)}</div>}
            </div>
          </article>)}
          {loading && <RequestStatus />}
        </div>}
        <div className={s.inputArea}>
          {hasMessages && <StudyCompanion compact name={firstName} mood={loading ? "thinking" : messages.at(-1)?.error ? "retry" : "happy"} />}
          <form className={s.glowFrame} onSubmit={submit}
            onDragOver={(event) => { if (event.dataTransfer.types.includes("Files")) { event.preventDefault(); event.dataTransfer.dropEffect = "none"; } }}
            onDrop={(event) => {
              if (!event.dataTransfer.files.length) return;
              event.preventDefault();
              toast.info("Image and file uploads are paused. Please type or paste your question text.");
            }}>
            <div className={s.composer}>
              <textarea ref={inputRef} value={question} readOnly={historyLoading} onChange={(event) => setQuestion(event.target.value)} onPaste={pasteQuestion}
                onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submitQuestion(question); } }}
                aria-label="Ask your CDS question" placeholder={firstName ? `Ask anything, ${firstName}…` : "Ask anything…"} rows={2} maxLength={1500} disabled={loading} />
              <div className={s.composerTools}>
                <div>
                  <label className={s.subjectSelect}><select aria-label="Question subject" value={subject} disabled={loading} onChange={(event) => setSubject(event.target.value as SubjectFilter)}><option value="all">All subjects</option><option value="general-knowledge">General knowledge</option><option value="elementary-mathematics">Mathematics</option><option value="english">English</option></select><ChevronDown size={12} /></label>
                </div>
                <button className={s.sendButton} type="submit" aria-label="Send question" disabled={!question.trim() || loading || historyLoading || !accessToken}>{loading ? <LoaderCircle size={18} className={s.spinner} /> : <ArrowUp size={20} />}</button>
              </div>
            </div>
          </form>
          <div className={s.inputHint}><span>Enter to send <span className={s.shiftHint}>· Shift + Enter for a new line</span></span></div>
        </div>
        {!hasMessages && <div className={s.suggestions} aria-label="Suggested questions">{prompts.map((prompt, index) => {
          const Icon = profile?.topics.length ? Sparkles : promptIcons[index];
          return <button key={prompt} disabled={loading || historyLoading} onClick={() => { setQuestion(prompt); inputRef.current?.focus(); }}><Icon size={17} /><span>{prompt}</span><ArrowUpRight size={13} /></button>;
        })}</div>}
      </div>
    </main>
    </div>
  </AppShell>;
}
