"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import AppShell from "../components/AppShell";
import { useAuth } from "../components/AuthProvider";
import PracticeWorkspace from "../practice/PracticeWorkspace";
import s from "../practice/practice.module.css";
import { getStudyTask, type StudyTask } from "@/lib/study-plan-api";

function SubjectsWorkspace() {
  const params = useSearchParams();
  const { user } = useAuth();
  const subject = params.get("subject") || "english";
  const topic = params.get("topic") || "";
  const view = params.get("view") === "history" ? "history" : "practice";
  const daily = params.get("daily");

  if (daily) return <DailyQuizWorkspace key={`${user?.id}:${daily}`} taskId={daily} />;

  return <PracticeWorkspace
    key={`${user?.id ?? "guest"}:${subject}:${topic}:${view}`}
    initialSubject={subject}
    initialTopic={topic}
    initialView={view}
  />;
}

function DailyQuizWorkspace({taskId}:{taskId:string}) {
  const {accessToken} = useAuth();
  const [task,setTask] = useState<StudyTask>();
  const [error,setError] = useState("");
  const [version,setVersion] = useState(0);
  useEffect(()=>{
    if(!accessToken)return;
    let alive=true;
    getStudyTask(accessToken,taskId).then(data=>{if(alive){setTask(data);setError("");}}).catch(e=>{if(alive)setError(e instanceof Error?e.message:"Couldn't open today's quiz.");});
    return()=>{alive=false;};
  },[accessToken,taskId,version]);
  if (!task) return <main className={s.workspace}><Link className={s.secondary} href="/progress#today">← Back to today’s plan</Link>{error?<div className={s.error} role="alert">{error}<button className={s.secondary} onClick={()=>setVersion(v=>v+1)}>Retry</button></div>:<div className={s.panel} role="status">Opening your topic quiz…</div>}</main>;
  if (task.completed || task.deferred || !task.study_done) return <main className={s.workspace}><section className={s.panel}><h1>{task.completed ? "Today’s target is complete" : task.deferred ? "This target is moved to tomorrow" : "Study this topic first"}</h1><p className={s.muted}>{task.subject_name} · {task.topic_name}</p><Link className={s.primary} href="/progress#today">Back to today’s plan →</Link></section></main>;
  return <PracticeWorkspace initialSubject={task.subject_slug} initialTopic={task.topic_slug} dailyTask={task} />;
}

export default function SubjectsPage() {
  return <AppShell active="Subjects">
    <Suspense fallback={<main className={s.workspace}><p className={s.muted} role="status">Opening your subjects…</p></main>}>
      <SubjectsWorkspace />
    </Suspense>
  </AppShell>;
}
