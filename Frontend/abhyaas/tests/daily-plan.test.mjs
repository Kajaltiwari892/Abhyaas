import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { dailyQuizHref, focusRemaining, nextStudyTask, quizAction, timetableTime, topicHelpHref } from "../lib/daily-plan.ts";

const task = (changes = {}) => ({id:"target-1",study_minutes:40,study_elapsed_seconds:0,study_started_at:null,study_done:false,completed:false,deferred:false,question_count:20,quiz_answered:0,quiz_remaining:20,quiz_status:null,...changes});

test("next focus ignores completed and deferred targets and keeps a running timer first", () => {
  const first=task(), running=task({id:"target-2",study_started_at:"2026-10-08T10:00:00Z"});
  assert.equal(nextStudyTask([task({completed:true}),task({deferred:true}),first,running]),running);
  assert.equal(nextStudyTask([task({completed:true}),task({deferred:true})]),undefined);
  assert.equal(nextStudyTask([first]),first);
});

test("focus countdown starts from saved server time, pauses and never goes negative", () => {
  assert.equal(focusRemaining(task({study_elapsed_seconds:60,study_started_at:"stamp"}),1000,31000),2310);
  assert.equal(focusRemaining(task({study_elapsed_seconds:60}),1000,31000),2340);
  assert.equal(focusRemaining(task({study_elapsed_seconds:2399,study_started_at:"stamp"}),1000,31000),0);
  assert.equal(focusRemaining(task({study_elapsed_seconds:60,study_started_at:"stamp"}),31000,1000),2340);
});

test("timetable displays noon, midnight and next-day slots clearly", () => {
  assert.equal(timetableTime(0),"12:00 am");
  assert.equal(timetableTime(720),"12:00 pm");
  assert.equal(timetableTime(1140),"7:00 pm");
  assert.equal(timetableTime(1465),"12:25 am (+1 day)");
});

test("quiz and help links keep the exact target and topic", () => {
  assert.equal(dailyQuizHref({id:"one&two"}),"/subjects?daily=one%26two");
  const help=new URL(topicHelpHref({topic_name:"Earth's interior",subject_slug:"general-knowledge"}),"http://localhost");
  assert.equal(help.pathname,"/doubt-solver");
  assert.equal(help.searchParams.get("subject"),"general-knowledge");
  assert.ok(help.searchParams.get("question").includes("Earth's interior"));
  assert.equal(quizAction(task()),"Take 20-question quiz");
  assert.equal(quizAction(task({quiz_status:"in_progress"})),"Resume quiz");
  assert.equal(quizAction(task({quiz_answered:2,quiz_remaining:18,quiz_status:"completed"})),"Finish 18 questions");
});

test("daily plan is above progress charts and exact-topic quizzes reuse the saved practice workflow", () => {
  const page=readFileSync(new URL("../app/progress/page.tsx",import.meta.url),"utf8");
  assert.ok(page.indexOf("<TodayPlan")<page.indexOf('id="stats"'));
  const workspace=readFileSync(new URL("../app/practice/PracticeWorkspace.tsx",import.meta.url),"utf8");
  assert.ok(workspace.includes("startDailyQuiz"));
  assert.ok(workspace.includes("dailyTask"));
  assert.ok(workspace.includes("setAnswers"));
  const ui=readFileSync(new URL("../app/progress/TodayPlan.tsx",import.meta.url),"utf8");
  assert.ok(ui.includes("Move to tomorrow"));
  assert.ok(ui.includes("Done studying"));
  assert.ok(ui.includes("role=\"progressbar\""));
  assert.ok(ui.includes("<dialog"));
});
