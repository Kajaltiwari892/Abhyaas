import type { StudyTask } from "./study-plan-api";

export function nextStudyTask(tasks: StudyTask[]): StudyTask | undefined {
  const pending = tasks.filter(t => !t.completed && !t.deferred);
  return pending.find(t => t.study_started_at && !t.study_done) ?? pending[0];
}

export function focusRemaining(task: StudyTask, receivedAt: number, now: number): number {
  const extra = task.study_started_at && !task.study_done
    ? Math.max(0, Math.floor((now - receivedAt) / 1000)) : 0;
  return Math.max(0, task.study_minutes * 60 - task.study_elapsed_seconds - extra);
}

export function timetableTime(minutes: number): string {
  const hour = Math.floor(minutes / 60) % 24;
  return `${hour % 12 || 12}:${String(minutes % 60).padStart(2, "0")} ${hour >= 12 ? "pm" : "am"}${minutes >= 1440 ? " (+1 day)" : ""}`;
}

export function dailyQuizHref(task: Pick<StudyTask, "id">): string {
  return `/subjects?daily=${encodeURIComponent(task.id)}`;
}

export function topicHelpHref(task: Pick<StudyTask, "topic_name" | "subject_slug">): string {
  const params = new URLSearchParams({
    question: `Help me study ${task.topic_name} for CDS. Explain the main ideas and common mistakes.`,
    subject: task.subject_slug,
  });
  return `/doubt-solver?${params}`;
}

export function quizAction(task: StudyTask): string {
  if (task.quiz_status === "in_progress") return "Resume quiz";
  if (task.curriculum_key && task.quiz_answered) return "Continue with a 50-question quiz";
  return task.quiz_answered ? `Finish ${task.quiz_remaining} questions` : `Take ${task.question_count}-question quiz`;
}
