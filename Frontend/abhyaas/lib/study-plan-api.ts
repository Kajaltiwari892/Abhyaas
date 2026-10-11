import { ApiError, apiRequest, sessionController } from "./auth-api";
import { createRequestCache } from "./request-cache";
import type { PracticeAttempt } from "./study-api";

export type StudyPreferences = {
  daily_minutes: number; start_time: string; subject_slugs: string[];
  configured: boolean; timezone: string; exam_date: string;
};
export type StudyTask = {
  id: string; plan_date: string; position: number;
  subject_slug: string; subject_name: string; topic_slug: string; topic_name: string;
  reason: "rotation" | "continue" | "weak_topic" | "learn" | "revision" | "catch-up";
  curriculum_key: string | null; focus_points: string[];
  start_minute: number; study_minutes: number; quiz_minutes: number; question_count: number;
  study_elapsed_seconds: number; study_started_at: string | null; study_done: boolean;
  deferred: boolean; completed: boolean; quiz_answered: number; quiz_correct: number;
  quiz_remaining: number; quiz_attempt_id: string | null; quiz_status: string | null;
};
export type StudyPlan = {
  id: string; plan_date: string; daily_minutes: number; start_time: string;
  completed_tasks: number; tasks: StudyTask[];
  version: number; checkin_seen: boolean;
};
export type StudyPlanDashboard = {
  today: string; preferences: StudyPreferences; plan: StudyPlan | null;
  settings_apply_tomorrow: boolean;
  roadmap_summary: RoadmapSummary | null;
  history: Array<{plan_date: string; completed_tasks: number; total_tasks: number; deferred_tasks: number}>;
};
const auth = (token: string, init: RequestInit = {}) => ({
  ...init, headers: { Authorization: `Bearer ${token}` },
});
const planCache = createRequestCache<StudyPlanDashboard>(10_000, 1);
const receivedTimes = new WeakMap<StudyPlanDashboard, number>();
export const planReceivedAt = (plan: StudyPlanDashboard) => receivedTimes.get(plan) ?? Date.now();
export const invalidateTodayPlan = () => planCache.clear();
let planGeneration = sessionController.getGeneration();
sessionController.subscribe(() => {
  const generation = sessionController.getGeneration();
  if (generation !== planGeneration) { planCache.clear(); planGeneration = generation; }
});
const planKey = (token: string) => {
  const session = sessionController.getSnapshot().session;
  return session && sessionController.ownsToken(token) ? session.user.id : token;
};
// Coalesce both the GET and any required plan creation, not just the first read.
export const getReadyTodayPlan = (token: string, signal?: AbortSignal) => {
  const generation = sessionController.getGeneration();
  return planCache.get(planKey(token), async () => {
    if (generation !== sessionController.getGeneration()) throw new ApiError("Your session has changed. Please try again.", 401);
    const requestSignal = AbortSignal.timeout(30_000);
    const result = await apiRequest<StudyPlanDashboard>("/study-plan/today", auth(token, { signal: requestSignal }));
    if (generation !== sessionController.getGeneration()) throw new ApiError("Your session has changed. Please try again.", 401);
    const ready = result.preferences.configured && (!result.plan || result.plan.version < 2)
      ? await apiRequest<StudyPlanDashboard>("/study-plan/today", auth(token, { method: "POST", signal: requestSignal }))
      : result;
    receivedTimes.set(ready, Date.now());
    return ready;
  }, signal);
};
const savePlan = async (token: string, request: Promise<StudyPlanDashboard>) => {
  // Invalidate reads before a write; an older GET must not overwrite this result.
  const generation = sessionController.getGeneration();
  const key = planKey(token);
  planCache.clear();
  const result = await request;
  receivedTimes.set(result, Date.now());
  if (generation === sessionController.getGeneration()) planCache.set(key, result);
  return result;
};
export const getTodayPlan = (token: string, signal?: AbortSignal) =>
  apiRequest<StudyPlanDashboard>("/study-plan/today", auth(token, { signal }));
export const createTodayPlan = (token: string, signal?: AbortSignal) =>
  savePlan(token, apiRequest<StudyPlanDashboard>("/study-plan/today", auth(token, { method: "POST", signal })));
export const saveStudyPreferences = (token: string, input: StudyPreferencesInput) =>
  savePlan(token, apiRequest<StudyPlanDashboard>("/study-plan/preferences", auth(token, {method:"PUT",body:JSON.stringify(input)})));
export const changeStudyTask = (token: string, id: string, action: "start" | "pause" | "complete" | "defer" | "restore", signal?: AbortSignal) =>
  savePlan(token, apiRequest<StudyPlanDashboard>(`/study-plan/tasks/${encodeURIComponent(id)}`, auth(token, {method:"PATCH",body:JSON.stringify({action}),signal})));
export const getStudyTask = (token: string, id: string, signal?: AbortSignal) =>
  apiRequest<StudyTask>(`/study-plan/tasks/${encodeURIComponent(id)}`, auth(token, {signal}));
export const startDailyQuiz = async (token: string, id: string, signal?: AbortSignal) => {
  planCache.clear();
  const result = await apiRequest<PracticeAttempt>(`/study-plan/tasks/${encodeURIComponent(id)}/quiz`, auth(token, {method:"POST", signal}));
  planCache.clear();
  return result;
};
export type StudyPreferencesInput = Pick<StudyPreferences, "daily_minutes" | "start_time" | "subject_slugs" | "exam_date">;
export type RoadmapDay = {
  date: string; phase: "learn" | "revision" | "catch-up" | "completed" | "unfinished";
  subject_slug: string; subject_name: string; topic_slug: string; topic_name: string;
  curriculum_key: string; focus_points: string[]; session: number; sessions: number;
  study_minutes: number; quiz_minutes: number; question_count: number;
};
export type RoadmapSummary = {
  exam_date: string; coverage_deadline: string; start_date: string; projected_finish: string | null;
  feasible: boolean; total_sessions: number; completed_sessions: number; unplaced_sessions: number; daily_minutes: number;
  syllabus_source: string; exam_source: string | null; current_affairs_note: string;
  units: Array<{key: string; subject_name: string; title: string; focus_points: string[]}>;
};
export type StudyRoadmap = RoadmapSummary & {days: RoadmapDay[]};
export const getStudyRoadmap = (token: string, signal?: AbortSignal) =>
  apiRequest<StudyRoadmap>("/study-plan/roadmap", auth(token, {signal}));
export const sendStudyCheckin = (token: string, task_id: string, answer: "yes" | "not-yet" | "dismiss") =>
  savePlan(token, apiRequest<StudyPlanDashboard>("/study-plan/checkin", auth(token, {method:"POST", body:JSON.stringify({task_id, answer})})));
