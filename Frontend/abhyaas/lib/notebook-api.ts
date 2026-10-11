import { apiRequest } from "./auth-api";

export type RevisionQuestion = {
  question_key: string;
  subject: string;
  subject_slug: string;
  topic: string;
  prompt: string;
  context: string | null;
  options: string[];
  source_label: string;
  source_url: string | null;
  source_page_url: string | null;
};

export type RevisionReview = RevisionQuestion & {
  selected_index: number | null;
  correct_index: number;
  explanation: string;
  is_correct: boolean;
};

export type NotebookEntry = Omit<RevisionReview, "is_correct"> & {
  reason: "wrong" | "skipped";
  state: "pending" | "resolved";
  last_attempt_at: string;
  // Optional while older deployments still return only the latest choice.
  mistake_selected_index?: number | null;
  revision_ready: boolean;
  review_available: boolean;
};

export type RevisionSession = {
  id: string;
  status: "in_progress" | "completed";
  current_position: number;
  started_at: string;
  completed_at: string | null;
  questions: RevisionQuestion[];
  answers: Record<string, number | null>;
};

export type RevisionResult = {
  id: string;
  completed_at: string;
  total_questions: number;
  correct_answers: number;
  wrong_answers: number;
  skipped_questions: number;
  review: RevisionReview[];
};

export type NotebookPage = {
  counts: { total: number; pending: number; resolved: number };
  items: NotebookEntry[];
  total: number;
  has_more: boolean;
  active_session: RevisionSession | null;
  revision_available: number;
  recent_sessions: Array<{ id: string; completed_at: string; total_questions: number; correct_answers: number }>;
};

export type NotebookFilters = {
  subject: string;
  reason: "all" | "wrong" | "skipped";
  state: "pending" | "resolved";
  offset: number;
};

const authorized = (token: string) => ({ Authorization: `Bearer ${token}` });

export function getNotebook(token: string, filters: NotebookFilters, signal?: AbortSignal) {
  const query = new URLSearchParams({ reason: filters.reason, state: filters.state, offset: String(filters.offset) });
  if (filters.subject) query.set("subject", filters.subject);
  return apiRequest<NotebookPage>(`/notebook?${query}`, { headers: authorized(token), signal });
}

export function startRevision(token: string, subject: string, reason: NotebookFilters["reason"], count: number) {
  return apiRequest<RevisionSession>("/notebook/sessions", {
    method: "POST", headers: authorized(token),
    body: JSON.stringify({ subject: subject || null, reason, question_count: count }),
  });
}

export function getRevision(token: string, id: string, signal?: AbortSignal) {
  return apiRequest<RevisionSession>(`/notebook/sessions/${encodeURIComponent(id)}`, { headers: authorized(token), signal });
}

export function getRevisionResult(token: string, id: string, signal?: AbortSignal) {
  return apiRequest<RevisionResult>(`/notebook/sessions/${encodeURIComponent(id)}/result`, { headers: authorized(token), signal });
}

function checkpoint(current: number, answers: RevisionSession["answers"]) {
  return JSON.stringify({ current_position: current, answers: Object.entries(answers).map(([question_key, selected_index]) => ({ question_key, selected_index })) });
}

export function saveRevision(token: string, id: string, current: number, answers: RevisionSession["answers"], keepalive = false) {
  return apiRequest<RevisionSession>(`/notebook/sessions/${encodeURIComponent(id)}`, {
    method: "PATCH", headers: authorized(token), body: checkpoint(current, answers), keepalive,
  });
}

export function finishRevision(token: string, id: string, current: number, answers: RevisionSession["answers"]) {
  return apiRequest<RevisionResult>(`/notebook/sessions/${encodeURIComponent(id)}/complete`, {
    method: "POST", headers: authorized(token), body: checkpoint(current, answers),
  });
}
