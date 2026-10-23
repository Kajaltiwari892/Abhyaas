"use client";

import { CalendarDays, ChevronLeft, ChevronRight, LoaderCircle, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { roadmapQuery } from "@/lib/study-plan-api";
import { calendarCells, roadmapDate, shiftMonth } from "@/lib/roadmap-calendar";
import s from "./today-plan.module.css";

export default function RoadmapCalendar({token,today,onClose}:{token:string;today:string;onClose:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null);
  const query=useQuery(roadmapQuery(token));
  const data=query.data;
  const error=query.error?.message;
  const [month,setMonth]=useState(today.slice(0,7));
  const [selected,setSelected]=useState(today);
  useEffect(()=>{dialog.current?.showModal();},[]);
  const day=data?.days.find(d=>d.date===selected);
  const phase=(value:string)=>({learn:"Study",revision:"Revision", "catch-up":"Catch-up",completed:"Complete",unfinished:"Unfinished"}[value]??"Study");
  return <dialog ref={dialog} className={`${s.dialog} ${s.calendarDialog}`} aria-labelledby="roadmap-title" onCancel={onClose} onClose={onClose}>
    <header><div><span className={s.eyebrow}><CalendarDays size={14}/> Your study roadmap</span><h3 id="roadmap-title">Small steps. A clear finish line.</h3></div><button aria-label="Close study calendar" onClick={onClose}><X size={20}/></button></header>
    {!data ? <p role={error?"alert":"status"}>{error ? <>{error} <button onClick={()=>void query.refetch()}>Retry</button></> : <><LoaderCircle size={16} className={s.spin}/> Opening your calendar…</>}</p> : <>
      <div className={s.calendarFacts}><span>First pass by <strong>{roadmapDate(data.coverage_deadline,{day:"numeric",month:"short",year:"numeric"})}</strong></span><span>Exam date <strong>{roadmapDate(data.exam_date,{day:"numeric",month:"short",year:"numeric"})}</strong></span><span>Daily time <strong>{data.daily_minutes} minutes</strong></span></div>
      {!data.feasible && <p className={s.warning} role="status">Your current pace is too tight for the first-pass deadline. Increase your daily time or adjust the exam date in Edit plan.{data.projected_finish && ` At this pace, the first pass finishes around ${roadmapDate(data.projected_finish)}.`}</p>}
      <div className={s.calendarLayout}><div><div className={s.monthHeading}><button aria-label="Previous month" disabled={month<=data.start_date.slice(0,7)} onClick={()=>setMonth(shiftMonth(month,-1))}><ChevronLeft size={18}/></button><strong>{roadmapDate(`${month}-01`,{month:"long",year:"numeric"})}</strong><button aria-label="Next month" disabled={month>=data.exam_date.slice(0,7)} onClick={()=>setMonth(shiftMonth(month,1))}><ChevronRight size={18}/></button></div><div className={s.calendarGrid}>
        {["M","T","W","T","F","S","S"].map((n,i)=><span key={i} className={s.weekday}>{n}</span>)}
        {calendarCells(month).map((date,i)=>{const item=data.days.find(d=>d.date===date);return date?<button key={date} disabled={!item} aria-pressed={selected===date} aria-label={`${roadmapDate(date)}${item?`, ${item.topic_name}, ${phase(item.phase)}`:""}`} data-phase={item?.phase} data-today={date===today} onClick={()=>setSelected(date)}>{Number(date.slice(-2))}<i/></button>:<span key={`blank-${i}`}/>;})}
      </div><div className={s.legend}><span><i data-phase="learn"/> Study</span><span><i data-phase="revision"/> Revision</span><span><i data-phase="completed"/> Complete</span><span><i data-phase="unfinished"/> Unfinished</span></div></div>
      <article className={s.dayDetail}><span className={s.eyebrow}>{roadmapDate(selected,{weekday:"long",day:"numeric",month:"short"})}</span>{day ? <><span className={s.phase}>{phase(day.phase)} · {day.subject_name}</span><h4>{day.topic_name}</h4>{day.sessions>1&&<small>Session {day.session} of {day.sessions}</small>}<ul>{day.focus_points.map(point=><li key={point}>{point}</li>)}</ul><p>{day.study_minutes} min study + {day.quiz_minutes} min quiz<br/><strong>{day.question_count} questions</strong></p>{day.date===today&&<button className={s.primary} onClick={onClose}>Go to today’s target</button>}</>:<p>No study session on this date.</p>}</article></div>
      <p className={s.calendarNote}>One topic at a time, with a weekly revision day. Missed sessions stay unfinished and are rescheduled. The last two months are for revision, current affairs and extra practice.</p>
      <details className={s.coverage}><summary>See the full subject roadmap · {data.units.length} topic groups</summary><div>{data.units.map(u=><span key={u.key}><small>{u.subject_name}</small><strong>{u.title}</strong></span>)}</div></details>
      <footer className={s.calendarFoot}>Abhyaas’s topic roadmap, based on the <a href={data.syllabus_source} target="_blank" rel="noreferrer">UPSC syllabus</a>. Time estimates help you plan; revise more where needed. {data.exam_source&&<a href={data.exam_source} target="_blank" rel="noreferrer">Exam calendar ↗</a>}</footer>
    </>}
  </dialog>;
}
