import { ApiError, apiRequest, sessionController } from "./auth-api";
import { assertSession, fetchCached, getQueryClient, invalidateStudyQueries, privateKey, privateQuery } from "./query-client";
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
const receivedTimes = new WeakMap<StudyPlanDashboard, number>();
export const planReceivedAt = (plan: StudyPlanDashboard) => receivedTimes.get(plan) ?? Date.now();
export const invalidateTodayPlan = () => invalidateStudyQueries(["today-plan", "roadmap"]);
// The read and any required creation are one shared operation. Never automatically
// replay a query containing a write after an ambiguous connection failure.
export const todayPlanQuery = (token: string | null) => ({
  ...privateQuery("today-plan", token, async signal => {
    const generation = sessionController.getGeneration();
    const result = await apiRequest<StudyPlanDashboard>("/study-plan/today", auth(token!, { signal }));
    assertSession(token, generation);
    signal.throwIfAborted();
    const ready = result.preferences.configured && (!result.plan || result.plan.version < 2)
      ? await apiRequest<StudyPlanDashboard>("/study-plan/today", auth(token!, { method: "POST", signal }))
      : result;
    receivedTimes.set(ready, Date.now());
    return ready;
  }, [], 30_000),
  retry: false,
  structuralSharing: false, // Timer baselines belong to this exact server response.
  refetchInterval: 60_000,
});
export const getReadyTodayPlan = (token: string, signal?: AbortSignal) => fetchCached(todayPlanQuery(token), signal);
const savePlan = (token: string, request: () => Promise<StudyPlanDashboard>) => {
  const client = getQueryClient();
  const key = privateKey("today-plan");
  // Check-in and task writes affect the same dashboard; serialize their responses.
  return client.getMutationCache().build(client, {
    mutationKey: key, scope: { id: JSON.stringify(key) }, retry: false,
    mutationFn: async () => {
      assertSession(token, key[1]);
      await client.cancelQueries({ queryKey: key });
      assertSession(token, key[1]);
      try {
        const result = await request();
        assertSession(token, key[1]);
        await client.cancelQueries({ queryKey: key });
        assertSession(token, key[1]);
        receivedTimes.set(result, Date.now());
        client.setQueryData(key, result, { updatedAt: Date.now() });
        invalidateStudyQueries(["roadmap"], key);
        return result;
      } catch (error) {
        invalidateStudyQueries(["today-plan"], key);
        throw error;
      }
    },
  }).execute(undefined);
};
export const getTodayPlan = (token: string, signal?: AbortSignal) =>
  apiRequest<StudyPlanDashboard>("/study-plan/today", auth(token, { signal }));
export const createTodayPlan = (token: string, signal?: AbortSignal) =>
  savePlan(token, () => apiRequest<StudyPlanDashboard>("/study-plan/today", auth(token, { method: "POST", signal })));
export const saveStudyPreferences = (token: string, input: StudyPreferencesInput) =>
  savePlan(token, () => apiRequest<StudyPlanDashboard>("/study-plan/preferences", auth(token, {method:"PUT",body:JSON.stringify(input)})));
export const changeStudyTask = (token: string, id: string, action: "start" | "pause" | "complete" | "defer" | "restore", signal?: AbortSignal) =>
  savePlan(token, () => apiRequest<StudyPlanDashboard>(`/study-plan/tasks/${encodeURIComponent(id)}`, auth(token, {method:"PATCH",body:JSON.stringify({action}),signal})));
export const getStudyTask = (token: string, id: string, signal?: AbortSignal) =>
  apiRequest<StudyTask>(`/study-plan/tasks/${encodeURIComponent(id)}`, auth(token, {signal}));
export type QuizPreparation = {
  status: "preparing" | "ready"; prepared_count: number; total: number;
  retry_after_ms: number; attempt: PracticeAttempt | null;
};
const waitForQuiz = (delay: number, signal?: AbortSignal) => new Promise<void>((resolve, reject) => {
  signal?.throwIfAborted();
  const abort = () => { clearTimeout(timer); reject(signal?.reason); };
  const timer = setTimeout(() => { signal?.removeEventListener("abort", abort); resolve(); }, delay);
  signal?.addEventListener("abort", abort, { once: true });
});
export const startDailyQuiz = async (token: string, id: string, signal?: AbortSignal, onProgress?: (prepared: number) => void) => {
  invalidateTodayPlan();
  const generation = sessionController.getGeneration();
  let failures = 0;
  // Every POST advances a durable draft by at most one short batch. Replaying
  // after an uncertain network outcome resumes it; it never makes another quiz.
  for (let step = 0; step < 150; step++) {
    signal?.throwIfAborted();
    if (generation !== sessionController.getGeneration()) throw new ApiError("Your session has changed. Please try again.", 401);
    let result: QuizPreparation;
    try {
      result = await apiRequest<QuizPreparation>(`/study-plan/tasks/${encodeURIComponent(id)}/quiz/prepare`, auth(token, {
        method: "POST", signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(60_000)]) : AbortSignal.timeout(60_000),
      }));
      failures = 0;
    } catch (error) {
      if (signal?.aborted) throw error;
      const transient = error instanceof ApiError && [0, 502, 504].includes(error.status)
        || error instanceof Error && error.name === "TimeoutError";
      if (!transient || ++failures > 2) throw error;
      await waitForQuiz(1500, signal);
      continue;
    }
    if (generation !== sessionController.getGeneration()) throw new ApiError("Your session has changed. Please try again.", 401);
    if (result.status === "ready" && result.attempt?.questions.length) {
      invalidateStudyQueries(["today-plan", "practice-history"]);
      return result.attempt;
    }
    if (result.status !== "preparing" || !Number.isInteger(result.prepared_count)
      || result.prepared_count < 0 || result.prepared_count > 50 || result.total !== 50) {
      throw new ApiError("Your quiz couldn't be opened. Please retry.", 502);
    }
    onProgress?.(result.prepared_count);
    await waitForQuiz(Math.min(5000, Math.max(200, result.retry_after_ms || 0)), signal);
  }
  throw new ApiError("Your prepared questions are saved. Please retry to finish opening the quiz.", 503);
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
export const roadmapQuery = (token: string | null) => privateQuery("roadmap", token,
  signal => apiRequest<StudyRoadmap>("/study-plan/roadmap", auth(token!, { signal })), [], 60_000);
export const getStudyRoadmap = (token: string, signal?: AbortSignal) => fetchCached(roadmapQuery(token), signal);
export const sendStudyCheckin = (token: string, task_id: string, answer: "yes" | "not-yet" | "dismiss") =>
  savePlan(token, () => apiRequest<StudyPlanDashboard>("/study-plan/checkin", auth(token, {method:"POST", body:JSON.stringify({task_id, answer})})));
