"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import type { CompanionMood, createCompanionScene } from "@/lib/companion-scene";
import s from "./study-companion.module.css";

export function CompanionMark({ className="" }: {className?:string}) {
  return <svg className={className} viewBox="0 0 32 32" fill="none" aria-hidden="true"><rect x="4" y="7" width="24" height="20" rx="8" fill="currentColor" opacity=".15"/><rect x="6" y="9" width="20" height="15" rx="6" stroke="currentColor" strokeWidth="1.5"/><path d="M10 16q2-4 4 0m4 0q2-4 4 0m-9 4q3 3 6 0M16 7V4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/><circle cx="16" cy="3" r="1.6" fill="currentColor"/></svg>;
}

export default function StudyCompanion({ mood="idle", compact=false, inline=false, name, variant="robot", size, voice=false }: {mood?:CompanionMood;compact?:boolean;inline?:boolean;name?:string;variant?:"robot"|"commando";size?:number;voice?:boolean}) {
  const host=useRef<HTMLDivElement>(null);
  const scene=useRef<ReturnType<typeof createCompanionScene> | null>(null);
  const currentMood=useRef(mood);
  const [ready,setReady]=useState(false);
  const [greeting,setGreeting]=useState(mood === "idle" || mood === "hello");
  const greetingTimer=useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(()=>{currentMood.current=mood;scene.current?.setMood(mood);},[mood]);
  useEffect(()=>{
    let cancelled=false;
    greetingTimer.current=setTimeout(()=>setGreeting(false),4000);
    // Give the composer its first paint before downloading WebGL. One canvas per page.
    const timer=window.setTimeout(()=>{
      void import("@/lib/companion-scene").then(({createCompanionScene})=>{
        if(cancelled||!host.current)return;
        try {scene.current=createCompanionScene(host.current,currentMood.current,variant);setReady(true);} catch { /* Illustration/vector fallback on devices without WebGL. */ }
      }).catch(()=>{});
    },350);
    return ()=>{cancelled=true;window.clearTimeout(timer);clearTimeout(greetingTimer.current);scene.current?.dispose();scene.current=null;};
  },[variant]);
  const sayHi=()=>{scene.current?.act("wave");setGreeting(true);clearTimeout(greetingTimer.current);greetingTimer.current=setTimeout(()=>setGreeting(false),3000);
    if(voice && "speechSynthesis" in window) {window.speechSynthesis.cancel();const hello=new SpeechSynthesisUtterance(`Hello${name?`, ${name}`:""}! One topic at a time. You've got this.`);hello.lang="en-IN";hello.rate=.95;window.speechSynthesis.speak(hello);}
  };
  const message=greeting?`Hi${name?`, ${name}`:""}! Let's learn something.`:mood==="thinking"?"Let’s look it up…":mood==="happy"?"One step clearer." :mood==="retry"?"Let’s try that again." :"Hi! What are we learning today?";
  return <div className={`${s.companion} ${compact?s.compact:""} ${inline?s.inline:""} ${size?s.stage:""}`} data-mood={mood} style={size?{width:size,height:size}:undefined}>
    <button type="button" className={s.character} aria-label="Say hi to your study companion" onClick={sayHi}
      onPointerMove={event=>{const r=event.currentTarget.getBoundingClientRect();scene.current?.look((event.clientX-r.left)/r.width-.5,(event.clientY-r.top)/r.height-.5);}}
      onPointerLeave={()=>scene.current?.look(0,0)}>
      <div className={s.scene} ref={host} aria-hidden="true" />
      {!ready&&(variant==="commando"?<Image src="/study-plan/companion.png" alt="" fill sizes="220px" className={s.illustrationFallback}/>:<CompanionMark className={s.fallback}/>)}
    </button>
    <span className={s.bubble} data-open={greeting} role="status">{message}</span>
  </div>;
}
