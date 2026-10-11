"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import AppShell from "../components/AppShell";
import { useAuth } from "../components/AuthProvider";
import PracticeWorkspace from "../practice/PracticeWorkspace";
import PracticeQuestionSkeleton from "../practice/PracticeQuestionSkeleton";
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
    const controller=new AbortController();
    const timeout=window.setTimeout(()=>controller.abort(),30_000);
    getStudyTask(accessToken,taskId,controller.signal).then(data=>{if(alive){setTask(data);setError("");}}).catch(e=>{if(alive)setError(controller.signal.aborted?"Opening your quiz took too long. Please retry.":e instanceof Error?e.message:"Couldn't open today's quiz.");}).finally(()=>window.clearTimeout(timeout));
    return()=>{alive=false;controller.abort();window.clearTimeout(timeout);};
  },[accessToken,taskId,version]);
  if (!task) return <main className={`${s.workspace} ${s.live}`}><header className={s.header}><h1>Today’s topic quiz</h1><Link className={s.secondary} href="/progress#today">← Today’s plan</Link></header>{error?<div className={s.error} role="alert">{error}<button className={s.secondary} onClick={()=>{setError("");setVersion(v=>v+1);}}>Retry</button></div>:<PracticeQuestionSkeleton count={50} />}</main>;
  if (task.completed || task.deferred || !task.study_done) return <main className={s.workspace}><section className={s.panel}><h1>{task.completed ? "Today’s target is complete" : task.deferred ? "This target is moved to tomorrow" : "Study this topic first"}</h1><p className={s.muted}>{task.subject_name} · {task.topic_name}</p><Link className={s.primary} href="/progress#today">Back to today’s plan →</Link></section></main>;
  return <PracticeWorkspace initialSubject={task.subject_slug} initialTopic={task.topic_slug} dailyTask={task} />;
}

export default function SubjectsPage() {
  return <AppShell active="Subjects">
    <Suspense fallback={<main className={`${s.workspace} ${s.live}`}><PracticeQuestionSkeleton /></main>}>
      <SubjectsWorkspace />
    </Suspense>
  </AppShell>;
}
