"use client";

import { ArrowUp, BookOpen, Bot, Headphones, Info, Mic, Paperclip, Sparkles } from "lucide-react";
import { useState } from "react";
import AppShell from "../components/AppShell";

const suggestions = [
  "Explain Fundamental Rights simply",
  "How do I solve time and work questions?",
  "Difference between weather and climate",
];

export default function DoubtSolverPage() {
  const [question, setQuestion] = useState("");

  return (
    <AppShell active="Doubt solver">
      <main className="workspace doubt-workspace">
        <header className="workspace-header">
          <div><span className="workspace-kicker">Source-grounded study help</span><h1>Ask Abhyaas</h1><p>Get an explanation, ask follow-ups, and check the material it came from.</p></div>
          <div className="workspace-badge"><Sparkles size={15} /> AI doubt solver</div>
        </header>

        <section className="chat-panel">
          <div className="chat-toolbar"><span><span className="status-dot" /> New conversation</span><button><Headphones size={15} /> Listen mode</button></div>
          <div className="chat-empty">
            <span className="chat-orb"><Bot size={30} /></span>
            <h2>What would you like to understand?</h2>
            <p>Ask about a CDS topic in your own words. Short questions work perfectly.</p>
            <div className="suggestion-grid">
              {suggestions.map((item) => <button key={item} onClick={() => setQuestion(item)}>{item}</button>)}
            </div>
          </div>
          <div className="composer-wrap">
            <div className="composer">
              <button aria-label="Attach material"><Paperclip size={18} /></button>
              <textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask your doubt here…" rows={1} />
              <button aria-label="Use voice input"><Mic size={19} /></button>
              <button className="send-button" aria-label="Send question" disabled={!question.trim()}><ArrowUp size={19} /></button>
            </div>
            <p><Info size={12} /> AI-generated explanations may be imperfect. Cross-check with official material.</p>
          </div>
        </section>

        <aside className="source-principle"><BookOpen size={18} /><div><strong>Answers show their sources</strong><p>When backend retrieval is connected, every response will cite the chapter or book used to prepare it.</p></div></aside>
      </main>
    </AppShell>
  );
}
