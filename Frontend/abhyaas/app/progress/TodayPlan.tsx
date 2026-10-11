"use client";

import { ArrowRight, BookOpen, CalendarDays, Check, Clock3, LoaderCircle, Pause, Play, RotateCcw, Settings2, Sparkles, Target, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent, type CSSProperties } from "react";
import { toast } from "sonner";
import { useAuth } from "../components/AuthProvider";
import { changeStudyTask, getReadyTodayPlan, planReceivedAt, saveStudyPreferences, type StudyPlanDashboard, type StudyPreferences, type StudyPreferencesInput, type StudyTask } from "@/lib/study-plan-api";
import { dailyQuizHref, focusRemaining, nextStudyTask, quizAction, timetableTime, topicHelpHref } from "@/lib/daily-plan";
import { roadmapDate } from "@/lib/roadmap-calendar";
import RoadmapCalendar from "./RoadmapCalendar";
import s from "./today-plan.module.css";

const clock=(seconds:number)=>`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,"0")}`;
const errorMessage=(error:unknown)=>error instanceof Error?error.message:"Couldn't save your plan. Try again.";

export default function TodayPlan() {
  const {user,accessToken}=useAuth();
  const [data,setData]=useState<StudyPlanDashboard>();
  const [receivedAt,setReceivedAt]=useState(0);
  const [now,setNow]=useState(0);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [pendingTaskAction,setPendingTaskAction]=useState<string|null>(null);
  const [editing,setEditing]=useState(false);
  const [calendar,setCalendar]=useState(false);
  const dialog=useRef<HTMLDialogElement>(null);
  const editTrigger=useRef<HTMLButtonElement>(null);
  const calendarTrigger=useRef<HTMLButtonElement>(null);
  const inFlight=useRef(false);
  const taskRequest=useRef<AbortController|null>(null);
  const loadVersion=useRef(0);
  const name=user?.name.trim().split(/\s+/)[0]??"";
  const accept=useCallback((result:StudyPlanDashboard)=>{setData(result);setReceivedAt(planReceivedAt(result));setNow(Date.now());setError("");},[]);
  const load=useCallback(async(signal?:AbortSignal)=>{
    if(!accessToken)return;
    const version=++loadVersion.current;
    const result=await getReadyTodayPlan(accessToken,signal);
    if(!signal?.aborted&&version===loadVersion.current)accept(result);
  },[accessToken,accept]);
  useEffect(()=>{const controller=new AbortController();void load(controller.signal).catch(e=>{if(!controller.signal.aborted)setError(errorMessage(e));});return()=>controller.abort();},[load]);
  useEffect(()=>{
    const controller=new AbortController();const tick=window.setInterval(()=>setNow(Date.now()),1000);
    const refresh=()=>{if(!inFlight.current&&!document.hidden)void load(controller.signal).catch(()=>{});};
    const interval=window.setInterval(refresh,60_000);
    window.addEventListener("focus",refresh);document.addEventListener("visibilitychange",refresh);window.addEventListener("abhyaas:plan-updated",refresh);
    return()=>{controller.abort();window.clearInterval(tick);window.clearInterval(interval);window.removeEventListener("focus",refresh);document.removeEventListener("visibilitychange",refresh);window.removeEventListener("abhyaas:plan-updated",refresh);};
  },[load]);
  useEffect(()=>{if(editing)dialog.current?.showModal();else if(dialog.current?.open)dialog.current.close();},[editing]);
  useEffect(()=>()=>{taskRequest.current?.abort();taskRequest.current=null;},[]);
  const updateTask=async(task:StudyTask,action:"start"|"pause"|"complete"|"defer"|"restore")=>{
    if(!accessToken||inFlight.current)return;
    const controller=new AbortController();taskRequest.current=controller;
    loadVersion.current++;inFlight.current=true;setBusy(true);setPendingTaskAction(action);setError("");
    const timeout=window.setTimeout(()=>controller.abort(),30_000);
    try{const result=await changeStudyTask(accessToken,task.id,action,controller.signal);if(taskRequest.current===controller&&!controller.signal.aborted)accept(result);}
    catch(e){if(taskRequest.current===controller)setError(controller.signal.aborted?"Saving your study progress took too long. Refresh your plan to check it, or try again.":errorMessage(e));}
    finally{window.clearTimeout(timeout);if(taskRequest.current===controller){taskRequest.current=null;inFlight.current=false;setBusy(false);setPendingTaskAction(null);}}
  };
  const save=async(preferences:StudyPreferencesInput)=>{
    if(!accessToken||inFlight.current)return;
    loadVersion.current++;inFlight.current=true;setBusy(true);setError("");
    try{const result=await saveStudyPreferences(accessToken,preferences);accept(result);setEditing(false);if(result.settings_apply_tomorrow)toast.success("Plan settings saved",{description:"They apply tomorrow. Today's progress stays saved."});}
    catch(e){setError(errorMessage(e));}finally{inFlight.current=false;setBusy(false);}
  };
  const plan=data?.plan;
  const next=nextStudyTask(plan?.tasks??[]);
  const running=!!next?.study_started_at&&!next.study_done;
  const remaining=next?focusRemaining(next,receivedAt,now):0;
  const roadmap=data?.roadmap_summary;
  const coverage=roadmap?Math.round(100*roadmap.completed_sessions/Math.max(1,roadmap.total_sessions)):0;
  return <section id="today" className={s.panel} aria-label="Today's study plan">
    <header className={s.header}><div><span className={s.eyebrow}><Sparkles size={14}/> Your study companion</span><h2>A little progress, every day.</h2><p>{data?roadmapDate(data.today,{weekday:"long",day:"numeric",month:"long"}):"A clear plan. A calmer day."}{name&&` · Let’s do this, ${name}.`}</p></div>{plan&&<button ref={editTrigger} className={s.editButton} onClick={()=>setEditing(true)}><Settings2 size={15}/> Edit plan</button>}</header>
    {error&&!editing&&<div className={s.error} role="alert">{error}<button onClick={()=>void load().catch(e=>setError(errorMessage(e)))}>Retry</button></div>}
    {!data?!error&&<div className={s.skeleton} role="status" aria-label="Loading today's plan"><span/><span/><span/></div>:!plan?<div className={s.setup}><div><h3>Your goal. Your pace.</h3><p>Choose your subjects and time. We’ll turn them into a dated plan, with a 50-question quiz after each study session.</p><Image src="/study-plan/companion.png" width={130} height={195} alt="Your smiling defence-themed study companion"/></div><PlanSettings initial={data.preferences} busy={busy} onSave={save}/></div>:<>
      {plan.daily_minutes>data.preferences.daily_minutes&&<p className={s.warning}>Today keeps your earlier study targets and saved time, with longer quizzes. Allow up to {plan.daily_minutes} minutes today; tomorrow’s plan uses your {data.preferences.daily_minutes}-minute daily budget.</p>}
      <div className={s.mainGrid}><article className={s.mission}>
        <div className={s.missionCopy}><span className={s.pill}><Target size={13}/>{next?.reason==="revision"?"Today’s revision":"Today’s mission"}</span><h3>{next?.topic_name??(plan.completed_tasks===plan.tasks.length?"Mission complete. Well done!":"A lighter day. Keep going.")}</h3><p>{next?`${next.subject_name} · ${next.study_minutes} min study · ${next.question_count} questions`:"Your progress is saved. Make some time to rest, too."}</p>
          {next&&<ul className={s.objectives}>{next.focus_points.map(point=><li key={point}><Check size={13}/>{point}</li>)}</ul>}
          <div className={s.missionActions}>{next?.study_done?<Link className={s.primary} prefetch={true} href={dailyQuizHref(next)}>{quizAction(next)}<ArrowRight size={15}/></Link>:next?<><button className={s.primary} disabled={busy} aria-busy={pendingTaskAction==="start"||pendingTaskAction==="pause"} onClick={()=>void updateTask(next,running?"pause":"start")}>{running?<Pause size={15}/>:<Play size={15}/>} {pendingTaskAction==="start"?"Starting study…":pendingTaskAction==="pause"?"Pausing study…":running?"Pause study":next.study_elapsed_seconds?"Resume study":"Start studying"}</button><button className={s.textButton} disabled={busy} onClick={()=>void updateTask(next,"complete")}><Check size={14}/> {pendingTaskAction==="complete"?"Saving…":"Done studying"}</button></>:null}</div>
          {next&&!next.study_done&&<Link className={s.topicHelp} href={topicHelpHref(next)}><BookOpen size={13}/> Need help with this topic? <ArrowRight size={12}/></Link>}
        </div><div className={s.missionArt}><span className={s.artHalo}/><Image src="/study-plan/companion.png" width={190} height={285} sizes="(max-width:600px) 105px, 190px" alt="A friendly study companion waving and holding a book" priority/>{next?<button className={s.helloButton} onClick={()=>window.dispatchEvent(new Event("abhyaas:open-checkin"))} aria-label="Say hello to your study companion">Say hello 👋</button>:<span className={s.artCaption}>One topic at a time.</span>}</div>
      </article><aside className={s.focusCard}><span className={s.eyebrow}><Clock3 size={14}/> Focus time</span><div className={s.timerRing} aria-busy={!!pendingTaskAction} style={{"--focus-progress":`${next?Math.min(100,(1-remaining/(next.study_minutes*60))*100):100}%`} as CSSProperties}><div>{pendingTaskAction?<><span className={s.focusSkeleton} aria-hidden="true"/><span role="status">{pendingTaskAction==="start"?"Starting your focus time…":"Saving your study progress…"}</span></>:<><strong>{next&&!next.study_done?clock(remaining):next?.study_done?"Ready":"Done"}</strong><span>{next?.study_done?"Time for your quiz":running?"You’re in your flow":"Make space to learn"}</span></>}</div></div><p>{next?.study_done?"50 questions to check your understanding.":"Put distractions aside. Start whenever you’re ready."}</p><span className={s.smallPill}>{plan.daily_minutes} min daily · {timetableTime(next?.start_minute??1140)} suggested</span></aside></div>
      <div className={s.lowerGrid}><button ref={calendarTrigger} className={s.roadmapCard} onClick={()=>setCalendar(true)}><span className={s.calendarIcon}><CalendarDays size={24}/></span><span><strong>Your path to April</strong><small>First pass by {roadmap?roadmapDate(roadmap.coverage_deadline):"February"}. Then revise with confidence.</small><span className={s.miniDates}>{[0,1,2,3,4,5,6].map(offset=>{const date=new Date(`${data.today}T12:00:00Z`);date.setUTCDate(date.getUTCDate()+offset);return <i key={offset} data-current={!offset}>{date.getUTCDate()}</i>;})}</span></span><span className={s.calendarCTA}>View calendar<ArrowRight size={15}/></span></button><div className={s.coverageCard}><span className={s.eyebrow}>First-pass progress</span><strong>{roadmap?.completed_sessions??0}<small> / {roadmap?.total_sessions??0} study sessions</small></strong><div className={s.progress} role="progressbar" aria-label="Syllabus study sessions completed" aria-valuemin={0} aria-valuemax={roadmap?.total_sessions??1} aria-valuenow={roadmap?.completed_sessions??0}><span style={{width:`${coverage}%`}}/></div><small>Counts studied topics with completed quizzes.</small></div></div>
      {roadmap&&!roadmap.feasible&&<p className={s.warning}>Your chosen pace needs more time to finish before {roadmapDate(roadmap.coverage_deadline)}. Open the calendar to see the forecast, or increase your daily time.</p>}
      <details className={s.schedule}><summary>Today’s schedule & recent days <span>{plan.completed_tasks}/{plan.tasks.length} complete</span></summary><ol className={s.tasks}>{plan.tasks.map(task=><li key={task.id}><span className={s.taskMark}>{task.completed?<Check size={16}/>:<BookOpen size={16}/>}</span><div><strong>{task.topic_name}</strong><p>{timetableTime(task.start_minute)} – {timetableTime(task.start_minute+task.study_minutes+task.quiz_minutes)} · {task.study_minutes} min study + {task.quiz_minutes} min quiz</p><small>{task.study_done?"Study done":"Study next"} · {task.quiz_answered}/{task.question_count} answered</small></div><div>{task.completed?<span className={s.done}><Check size={13}/> Complete</span>:task.deferred?<button className={s.textButton} disabled={busy} onClick={()=>void updateTask(task,"restore")}><RotateCcw size={13}/> Bring back</button>:<button className={s.textButton} disabled={busy} onClick={()=>void updateTask(task,"defer")}>Move to tomorrow</button>}</div></li>)}</ol><div className={s.recentDays}>{data.history.map(day=><span key={day.plan_date}><strong>{roadmapDate(day.plan_date)}</strong><small>{day.completed_tasks}/{day.total_tasks} complete</small></span>)}</div></details>
    </>}
    <dialog ref={dialog} className={s.dialog} aria-labelledby="edit-plan-title" onCancel={()=>setEditing(false)} onClose={()=>{setEditing(false);editTrigger.current?.focus();}}><header><h3 id="edit-plan-title">Make the plan yours</h3><button onClick={()=>setEditing(false)} aria-label="Close plan settings"><X size={20}/></button></header><p>Started targets stay saved. Changes to their timetable apply tomorrow.</p>{error&&editing&&<p className={s.error} role="alert">{error}</p>}{data&&editing&&<PlanSettings initial={data.preferences} busy={busy} onSave={save} editing/>}</dialog>
    {calendar&&accessToken&&data&&<RoadmapCalendar token={accessToken} today={data.today} onClose={()=>{setCalendar(false);calendarTrigger.current?.focus();}}/>}
  </section>;
}

function PlanSettings({initial,busy,onSave,editing=false}:{initial:StudyPreferences;busy:boolean;onSave:(p:StudyPreferencesInput)=>Promise<void>;editing?:boolean}) {
  const [minutes,setMinutes]=useState(initial.daily_minutes);
  const [start,setStart]=useState(initial.start_time);
  const [subjects,setSubjects]=useState(initial.subject_slugs);
  const [exam,setExam]=useState(initial.exam_date);
  const submit=(e:FormEvent)=>{e.preventDefault();void onSave({daily_minutes:minutes,start_time:start,subject_slugs:subjects,exam_date:exam});};
  return <form className={s.settings} onSubmit={submit}><div className={s.fields}><label>Daily time<select value={minutes} onChange={e=>setMinutes(Number(e.target.value))} disabled={busy}>{[30,60,90,120,180].map(n=><option key={n} value={n}>{n} minutes</option>)}</select></label><label>Usually start at<input type="time" value={start} onChange={e=>setStart(e.target.value)} required disabled={busy}/><small>Indian Standard Time</small></label></div><label>Exam date<input type="date" value={exam} onChange={e=>setExam(e.target.value)} required disabled={busy}/><small>The first-pass deadline is two months earlier.</small></label><fieldset disabled={busy}><legend>Your subjects</legend>{[{slug:"english",label:"English"},{slug:"general-knowledge",label:"General Knowledge"},{slug:"elementary-mathematics",label:"Mathematics (not required for OTA)"}].map(subject=><label key={subject.slug}><input type="checkbox" checked={subjects.includes(subject.slug)} onChange={e=>setSubjects(current=>e.target.checked?[...current,subject.slug]:current.filter(slug=>slug!==subject.slug))}/>{subject.label}</label>)}</fieldset>{!subjects.length&&<p className={s.error}>Choose at least one subject.</p>}<button className={s.primary} disabled={busy||!subjects.length||!start||!exam}>{busy?<LoaderCircle size={15} className={s.spin}/>:<Sparkles size={15}/>} {busy?"Saving your plan…":editing?"Save plan settings":"Make my daily plan"}<ArrowRight size={15}/></button></form>;
}
