import { apiRequest } from "./auth-api";

export type Topic = { id: string; slug: string; name: string };
export type Subject = {
  id: string;
  slug: string;
  code: string;
  name: string;
  description: string;
  topics: Topic[];
};

export type PracticeQuestion = {
  id: string;
  position: number;
  subject: string;
  topic: string;
  prompt: string;
  context: string | null;
  options: string[];
};

export type PracticeAttempt = {
  id: string;
  subject: string;
  topic: string | null;
  started_at: string;
  duration_seconds: number;
  questions: PracticeQuestion[];
};

export type AttemptSummary = {
  attempt_id: string;
  total_questions: number;
  answered_questions: number;
  correct_answers: number;
  accuracy: number;
  duration_seconds: number;
  review: Array<{
    question_id: string;
    selected_index: number | null;
    correct_index: number;
    is_correct: boolean;
    explanation: string;
    source_label: string;
  }>;
};

export type ProgressDashboard = {
  completed_sets: number;
  questions_attempted: number;
  correct_answers: number;
  overall_accuracy: number | null;
  practice_seconds: number;
  subject_strengths: Array<{ subject: string; attempted: number; accuracy: number | null }>;
  history: Array<{
    attempt_id: string;
    subject: string;
    topic: string | null;
    completed_at: string;
    correct_answers: number;
    total_questions: number;
    accuracy: number;
    duration_seconds: number;
  }>;
  trend: Array<{ date: string; accuracy: number }>;
};

const authorized = (token: string, init: RequestInit = {}): RequestInit => ({
  ...init,
  headers: { Authorization: `Bearer ${token}`, ...init.headers },
});

export const getSubjects = () => apiRequest<Subject[]>("/catalog/subjects");

export const startPracticeAttempt = (
  token: string,
  input: { subject_slug: string; topic_slug?: string; question_count?: number },
) => apiRequest<PracticeAttempt>("/practice/attempts", authorized(token, { method: "POST", body: JSON.stringify(input) }));

export const savePracticeAnswer = (
  token: string,
  attemptId: string,
  questionId: string,
  input: { selected_index: number; marked_for_review: boolean },
) => apiRequest(`/practice/attempts/${attemptId}/answers/${questionId}`, authorized(token, { method: "PUT", body: JSON.stringify(input) }));

export const completePracticeAttempt = (token: string, attemptId: string, durationSeconds: number) =>
  apiRequest<AttemptSummary>(`/practice/attempts/${attemptId}/complete`, authorized(token, { method: "POST", body: JSON.stringify({ duration_seconds: durationSeconds }) }));

export const getProgressDashboard = (token: string) =>
  apiRequest<ProgressDashboard>("/progress/dashboard", authorized(token));
