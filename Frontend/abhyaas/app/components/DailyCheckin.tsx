"use client";

import { ArrowRight, BookOpen, LoaderCircle, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getReadyTodayPlan, sendStudyCheckin, type StudyTask } from "@/lib/study-plan-api";
import { dailyQuizHref, nextStudyTask } from "@/lib/daily-plan";
import { useAuth } from "./AuthProvider";
import StudyCompanion from "./StudyCompanion";
import s from "./daily-checkin.module.css";

export default function DailyCheckin() {
  const {user,accessToken}=useAuth();
  const userId=user?.id;
  const router=useRouter();
  const [task,setTask]=useState<StudyTask>();
  const [reply,setReply]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [dismissed,setDismissed]=useState(false);
  const inFlight=useRef(false);
  const manualOpen=useRef(false);
  const closedDay=useRef("");
  useEffect(()=>{
    if(!userId || !accessToken)return;
    const controller=new AbortController();
    const load=async()=>{
      if(inFlight.current || document.hidden)return;
      try {
        const result=await getReadyTodayPlan(accessToken,controller.signal);
        if(controller.signal.aborted)return;
        if(closedDay.current && closedDay.current!==result.today){closedDay.current="";setReply(false);setDismissed(false);}
        const next=nextStudyTask(result.plan?.tasks??[]);
        setTask(manualOpen.current || (!result.plan?.checkin_seen && result.today!==closedDay.current)?next:undefined);
      } catch { /* The planner has its own retry UI; a check-in must not block navigation. */ }
    };
    const open=()=>{manualOpen.current=true;setDismissed(false);setReply(false);void load();};
    void load();const interval=window.setInterval(()=>void load(),60_000);
    window.addEventListener("focus",load);
    window.addEventListener("abhyaas:open-checkin",open);
    return()=>{controller.abort();window.clearInterval(interval);window.removeEventListener("focus",load);window.removeEventListener("abhyaas:open-checkin",open);};
  },[userId,accessToken]);
  const answer=async(choice:"yes"|"not-yet"|"dismiss")=>{
    if(!accessToken || !task || inFlight.current)return;
    inFlight.current=true;setBusy(true);setError("");
    try {
      await sendStudyCheckin(accessToken,task.id,choice);
      manualOpen.current=choice==="not-yet";
      closedDay.current=task.plan_date;
      window.dispatchEvent(new Event("abhyaas:plan-updated"));
      if(choice==="yes"){setDismissed(true);router.push(dailyQuizHref(task));}
      else if(choice==="dismiss")setDismissed(true);
      else setReply(true);
    } catch(e){setError(e instanceof Error?e.message:"Couldn't save your check-in. Try again.");}
    finally{inFlight.current=false;setBusy(false);}
  };
  if(!task || dismissed)return null;
  const name=user?.name.trim().split(/\s+/)[0];
  return <aside className={s.card} aria-labelledby="daily-checkin-title">
    <button className={s.close} aria-label="Close daily check-in" disabled={busy} onClick={()=>reply?setDismissed(true):void answer("dismiss")}><X size={18}/></button>
    <div className={s.character}><StudyCompanion variant="commando" size={155} mood={reply?"happy":"hello"} name={name} voice/><small>Tap me to hear hello</small></div>
    <div className={s.copy}><span className={s.label}><Sparkles size={13}/> Your daily companion</span><h2 id="daily-checkin-title">{reply?"No rush. One step at a time.":`Hey${name?`, ${name}`:""}! Ready for today?`}</h2><p>{reply?`Take a little time to study ${task.topic_name.toLowerCase()}. Your quiz will be ready when you are.`:"Have you studied today’s topic?"}</p>{!reply&&<strong>{task.topic_name}</strong>}
      {error&&<p className={s.error} role="alert">{error}</p>}
      <div className={s.actions}>{reply?<Link href="/progress#today" onClick={()=>setDismissed(true)}>See today’s plan <ArrowRight size={14}/></Link>:<><button disabled={busy} onClick={()=>void answer("yes")}>{busy?<LoaderCircle size={15} className={s.spin}/>:<BookOpen size={15}/>} Yes, take the quiz</button><button disabled={busy} onClick={()=>void answer("not-yet")}>Not yet</button></>}</div>
    </div>
  </aside>;
}
