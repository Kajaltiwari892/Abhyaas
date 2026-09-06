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
    scored_questions: number;
    accuracy: number | null;
    duration_seconds: number;
  }>;
  trend: Array<{ date: string; accuracy: number }>;
};

export type PaperListItem = {
  id: string;
  year: number;
  cycle: "I" | "II";
  title: string;
  subject_slug: string;
  subject_name: string;
  exam_date: string;
  duration_seconds: number;
  total_marks: number;
  official_question_count: number;
  available_question_count: number;
  verified_question_count: number;
  academy_tracks: string[];
  source_url: string;
  solutions_available: boolean;
};

export type PaperQuestion = {
  id: string;
  number: number;
  topic: string | null;
  prompt: string;
  context: string | null;
  options: string[];
  asset_url: string | null;
  is_verified: boolean;
};

export type PaperSolution = PaperQuestion & {
  correct_index: number | null;
  explanation: string | null;
  source_label: string;
};

export type PaperDetail = PaperListItem & {
  negative_mark_fraction: number;
  questions: PaperSolution[];
};

export type PaperAttempt = {
  id: string;
  paper_id: string;
  title: string;
  started_at: string;
  duration_seconds: number;
  questions: PaperQuestion[];
};

export type PaperAttemptSummary = {
  attempt_id: string;
  total_questions: number;
  answered_questions: number;
  scored_questions: number;
  unscored_questions: number;
  correct_answers: number;
  incorrect_answers: number;
  unanswered_questions: number;
  score: number | null;
  max_score: number | null;
  accuracy: number | null;
  duration_seconds: number;
  review: Array<{
    question_id: string;
    selected_index: number | null;
    correct_index: number | null;
    is_correct: boolean | null;
    explanation: string | null;
    source_label: string;
  }>;
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

export const getPapers = (filters: { year?: number; cycle?: string; subject?: string } = {}) => {
  const params = new URLSearchParams();
  if (filters.year) params.set("year", String(filters.year));
  if (filters.cycle) params.set("cycle", filters.cycle);
  if (filters.subject) params.set("subject", filters.subject);
  const query = params.size ? `?${params.toString()}` : "";
  return apiRequest<PaperListItem[]>(`/papers${query}`);
};

export const getPaper = (token: string, paperId: string) =>
  apiRequest<PaperDetail>(`/papers/${paperId}`, authorized(token));

export const startPaperAttempt = (token: string, paperId: string) =>
  apiRequest<PaperAttempt>(`/papers/${paperId}/attempts`, authorized(token, { method: "POST" }));

export const savePaperAnswer = (
  token: string,
  attemptId: string,
  questionId: string,
  input: { selected_index: number; marked_for_review: boolean },
) => apiRequest(
  `/paper-attempts/${attemptId}/answers/${questionId}`,
  authorized(token, { method: "PUT", body: JSON.stringify(input) }),
);

export const completePaperAttempt = (
  token: string,
  attemptId: string,
  durationSeconds: number,
  answers: Array<{ question_id: string; selected_index: number; marked_for_review: boolean }> = [],
) =>
  apiRequest<PaperAttemptSummary>(
    `/paper-attempts/${attemptId}/complete`,
    authorized(token, { method: "POST", body: JSON.stringify({ duration_seconds: durationSeconds, answers }) }),
  );
