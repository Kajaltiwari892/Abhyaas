"use client";

import { ArrowRight, BookOpen, LoaderCircle, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { todayPlanQuery, sendStudyCheckin } from "@/lib/study-plan-api";
import { dailyQuizHref, nextStudyTask } from "@/lib/daily-plan";
import { useAuth } from "./AuthProvider";
import StudyCompanion from "./StudyCompanion";
import s from "./daily-checkin.module.css";

export default function DailyCheckin() {
  const {user,accessToken}=useAuth();
  const router=useRouter();
  const query=useQuery(todayPlanQuery(accessToken));
  const today=query.data?.today ?? "";
  const [interaction,setInteraction]=useState({day:"",manual:false,reply:false,closed:false});
  const current=interaction.day===today?interaction:{day:today,manual:false,reply:false,closed:false};
  const reply=current.reply;
  const task=nextStudyTask(query.data?.plan?.tasks??[]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const inFlight=useRef(false);
  useEffect(()=>{
    const open=()=>{setInteraction({day:today,manual:true,reply:false,closed:false});};
    window.addEventListener("abhyaas:open-checkin",open);
    return()=>window.removeEventListener("abhyaas:open-checkin",open);
  },[today]);
  const answer=async(choice:"yes"|"not-yet"|"dismiss")=>{
    if(choice==="dismiss") {
      setInteraction({day:today,manual:false,reply:false,closed:true});
      if(accessToken && task) void sendStudyCheckin(accessToken,task.id,choice).catch(()=>{});
      return;
    }
    if(!accessToken || !task || inFlight.current)return;
    inFlight.current=true;setBusy(true);setError("");
    try {
      await sendStudyCheckin(accessToken,task.id,choice);
      if(choice==="yes"){setInteraction({day:today,manual:false,reply:false,closed:true});router.push(dailyQuizHref(task));}
      else setInteraction(previous=>previous.day===today&&previous.closed?previous:{day:today,manual:true,reply:true,closed:false});
    } catch(e){setError(e instanceof Error?e.message:"Couldn't save your check-in. Try again.");}
    finally{inFlight.current=false;setBusy(false);}
  };
  if(!task || current.closed || (!current.manual && query.data?.plan?.checkin_seen))return null;
  const name=user?.name.trim().split(/\s+/)[0];
  return <aside className={s.card} aria-labelledby="daily-checkin-title">
    <button className={s.close} aria-label="Close daily check-in" onClick={()=>void answer("dismiss")}><X size={18}/></button>
    <div className={s.character}><StudyCompanion variant="commando" size={155} mood={reply?"happy":"hello"} name={name} voice/><small>Tap me to hear hello</small></div>
    <div className={s.copy}><span className={s.label}><Sparkles size={13}/> Your daily companion</span><h2 id="daily-checkin-title">{reply?"No rush. One step at a time.":`Hey${name?`, ${name}`:""}! Ready for today?`}</h2><p>{reply?`Take a little time to study ${task.topic_name.toLowerCase()}. Your quiz will be ready when you are.`:"Have you studied today’s topic?"}</p>{!reply&&<strong>{task.topic_name}</strong>}
      {error&&<p className={s.error} role="alert">{error}</p>}
      <div className={s.actions}>{reply?<Link href="/progress#today" onClick={()=>setInteraction({day:today,manual:false,reply:false,closed:true})}>See today’s plan <ArrowRight size={14}/></Link>:<><button disabled={busy} onClick={()=>void answer("yes")}>{busy?<LoaderCircle size={15} className={s.spin}/>:<BookOpen size={15}/>} Yes, take the quiz</button><button disabled={busy} onClick={()=>void answer("not-yet")}>Not yet</button></>}</div>
    </div>
  </aside>;
}
