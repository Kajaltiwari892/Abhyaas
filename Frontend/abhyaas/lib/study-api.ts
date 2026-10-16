import { apiRequest } from "./auth-api";
import { createRequestCache } from "./request-cache";
import { invalidateTodayPlan } from "./study-plan-api";

export type Topic = { id: string; slug: string; name: string; question_count: number };
export type Subject = {
  id: string;
  slug: string;
  code: string;
  name: string;
  description: string;
  topics: Topic[];
  question_count: number;
};

export type PracticeProvenance = { kind: "pyq"; source_url: string; source_page_url: string; answer_key_url: string | null; answer_basis?: "official" | "provisional" | "reviewed"; text_reviewed: boolean; year: number; cycle: string; number: number } | { kind: "generated"; answer_verified: false };
export type PracticeQuestion = {
  id: string;
  position: number;
  subject: string;
  topic: string;
  prompt: string;
  context: string | null;
  options: string[];
  source_label: string;
  provenance: PracticeProvenance | null;
};

export type PracticeAttempt = {
  id: string;
  subject: string;
  topic: string | null;
  started_at: string;
  duration_seconds: number;
  questions: PracticeQuestion[];
  subject_slug: string;
  topic_slug: string | null;
  status: string;
  elapsed_seconds: number;
  current_position: number;
  negative_mark_fraction: number;
  new_questions: number;
  repeated_questions: number;
  question_mode: "bank" | "similar" | "daily";
  answers: PracticeAnswerInput[];
};

export type PracticeAnswerInput = { question_id: string; selected_index: number; marked_for_review: boolean };
export type PracticeHistoryItem = {
  id: string; subject: string; topic: string | null; status: string; started_at: string;
  completed_at: string | null; total_questions: number; answered_questions: number;
  correct_answers: number | null; duration_seconds: number; time_limit_seconds: number;
  question_mode: "bank" | "similar" | "daily";
};
export type PageResult<T> = { items: T[]; total: number; has_more: boolean };
export type CatalogQuestionPage = { questions: PracticeQuestion[]; total: number; has_more: boolean };

export type AttemptSummary = {
  attempt_id: string;
  subject: string;
  topic: string | null;
  total_questions: number;
  answered_questions: number;
  correct_answers: number;
  accuracy: number;
  score: number;
  negative_mark_fraction: number;
  duration_seconds: number;
  question_mode: "bank" | "similar" | "daily";
  review: Array<{
    question_id: string;
    selected_index: number | null;
    correct_index: number;
    is_correct: boolean;
    explanation: string;
    source_label: string;
    provenance: PracticeProvenance | null;
    position: number; prompt: string; context: string | null; options: string[]; topic: string;
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
  exam_date: string | null;
  duration_seconds: number;
  total_marks: number;
  official_question_count: number;
  available_question_count: number;
  verified_question_count: number;
  scorable_question_count: number;
  reviewed_question_count: number;
  academy_tracks: string[];
  source_url: string;
  solutions_available: boolean;
};

export type PaperTranscription = {
  prompt: string; options: string[]; sectionTitle?: string; directions?: string;
  passage?: string; hasVisual?: boolean; visualDescription?: string; sourcePageUrl?: string;
  text_reviewed?: boolean;
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
  is_scorable: boolean;
  answer_basis: "official" | "provisional" | "reviewed" | "pending";
  transcription: PaperTranscription | null;
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
  elapsed_seconds: number;
  resumed: boolean;
  answers: PaperSavedAnswer[];
  questions: PaperQuestion[];
};

export type PaperSavedAnswer = {
  question_id: string;
  selected_index: number;
  marked_for_review: boolean;
  is_correct: boolean | null;
  correct_index: number | null;
};

export type PaperAttemptSummary = {
  attempt_id: string;
  total_questions: number;
  answered_questions: number;
  scored_questions: number;
  unscored_questions: number;
  official_answers: number;
  reviewed_answers: number;
  provisional_answers: number;
  score_basis: "official" | "practice";
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
    answer_basis: "official" | "provisional" | "reviewed" | "pending";
  }>;
};

export type PaperAIExplanation = {
  correct_index: number;
  explanation: string;
  confidence: "high" | "medium" | "low";
};

export type DoubtSource = {
  id: string;
  title: string;
  publisher: string;
  chapter: string | null;
  page_start: number | null;
  page_end: number | null;
  source_url: string | null;
  excerpt: string;
  relevance: number;
};

export type DoubtAnswer = {
  conversation_id: string;
  answer: string;
  confidence: number;
  grounded: boolean;
  sources: DoubtSource[];
  follow_up_questions: string[];
  pyq_result: PyqResult | PaperSolutionResult | null;
  practice_result: PracticeResult | null;
  answer_kind: "explanation" | "pyq" | "practice" | "clarification" | "archive_info" | "paper_solution";
};

export type PyqCard = {
  id: string; paper_id: string; number: number; year: number; cycle: string; subject: string;
  prompt: string; options: string[]; directions?: string; passage?: string; section_title?: string;
  has_visual: boolean; source_page?: number; source_page_url?: string; source_url: string;
  topics: string[]; text_reviewed: boolean; answer_verified: boolean;
  answer_scorable?: boolean; answer_basis?: "official" | "provisional" | "reviewed" | "pending";
  correct_index: number | null; explanation: string | null;
};
export type PyqResult = {
  questions: PyqCard[]; total: number; returned: number; has_more: boolean;
  indexed_questions: number; catalog_questions: number; kind: "pyq" | "clarification" | "archive_info";
  query: { years: number[]; cycle: string | null; chapter: string | null; subject: string | null; offset: number };
};

export type PaperSolutionResult = {
  kind: "paper_solution";
  status: "solutions" | "clarification" | "unavailable" | "complete";
  paper: { id: string; title: string; total: number; source_url: string } | null;
  start: number; end: number; next_number: number; range_end: number | null; has_more: boolean;
  questions: Array<{
    id: string; number: number; prompt: string; options: string[];
    directions?: string | null; passage?: string | null; additional_context?: string | null;
    text_reviewed: boolean; source_url: string;
    solution: { status: "ai" | "verified" | "reviewed" | "provisional" | "needs_source" | "uncertain" | "key_conflict" | "key_pending";
      answer_index: number | null; explanation: string };
  }>;
};

export type PracticeResult = {
  kind: "practice" | "clarification"; topic: string; requested: number; target: number;
  returned: number; complete: boolean;
  questions: Array<{number: number; prompt: string; options: string[]; correct_index: number; explanation: string}>;
};

export type DoubtImage = { mime_type: "image/jpeg" | "image/png" | "image/webp"; data: string };
export type StudyProfile = {
  enabled: boolean;
  explanation_style: "step-by-step" | "concise" | "hints-first";
  topics: Array<{ name: string; count: number }>;
  total_questions: number;
  suggested_questions: string[];
};

const authorized = (token: string, init: RequestInit = {}): RequestInit => ({
  ...init,
  headers: { Authorization: `Bearer ${token}`, ...init.headers },
});

const subjectCache = createRequestCache<Subject[]>(300_000, 1);
const paperListCache = createRequestCache<PaperListItem[]>(60_000);
export const getSubjects = () => subjectCache.get("subjects", () =>
  apiRequest<Subject[]>("/catalog/subjects", { signal: AbortSignal.timeout(20_000) }));

export const startPracticeAttempt = (
  token: string,
  input: { subject_slug: string; topic_slug?: string; question_count?: number; allow_repeats?: boolean },
  signal?: AbortSignal,
) => apiRequest<PracticeAttempt>("/practice/attempts", authorized(token, { method: "POST", body: JSON.stringify(input), signal }));

export const startSimilarAttempt = (
  token: string,
  input: { subject_slug: string; topic_slug?: string; question_count: number },
  signal?: AbortSignal,
) => apiRequest<PracticeAttempt>("/practice/attempts/similar", authorized(token, {
  method: "POST", body: JSON.stringify(input), signal,
}));

export const savePracticeAnswer = (
  token: string,
  attemptId: string,
  questionId: string,
  input: { selected_index: number; marked_for_review: boolean },
) => apiRequest(`/practice/attempts/${attemptId}/answers/${questionId}`, authorized(token, { method: "PUT", body: JSON.stringify(input) }));

export const completePracticeAttempt = async (token: string, attemptId: string, durationSeconds: number, answers: PracticeAnswerInput[] = []) => {
  const result = await apiRequest<AttemptSummary>(`/practice/attempts/${attemptId}/complete`, authorized(token, { method: "POST", body: JSON.stringify({ duration_seconds: durationSeconds, answers }) }));
  invalidateTodayPlan();
  return result;
};

export const checkpointPracticeAttempt = (token: string, attemptId: string, durationSeconds: number, answers: PracticeAnswerInput[], currentPosition?: number, keepalive = false) =>
  apiRequest<null>(`/practice/attempts/${attemptId}`, authorized(token, { method: "PATCH", keepalive, signal: AbortSignal.timeout(20_000), body: JSON.stringify({ duration_seconds: durationSeconds, answers, current_position: currentPosition }) }));
export type PracticeAvailability = { total: number; unseen: number; seen: number };
export const getPracticeAvailability = (token: string, subject: string, topic = "") => {
  const params = new URLSearchParams({ subject_slug: subject });
  if (topic) params.set("topic_slug", topic);
  return apiRequest<PracticeAvailability>(`/practice/availability?${params}`, authorized(token));
};
export const getPracticeHistory = (token: string, offset = 0) =>
  apiRequest<PageResult<PracticeHistoryItem>>(`/practice/attempts?offset=${offset}&limit=20`, authorized(token));
export const getPracticeAttempt = (token: string, id: string) => apiRequest<PracticeAttempt>(`/practice/attempts/${id}`, authorized(token));
export const getPracticeResult = (token: string, id: string) => apiRequest<AttemptSummary>(`/practice/attempts/${id}/result`, authorized(token));
export const getCatalogQuestions = (subject: string, topic = "", offset = 0) => {
  const params = new URLSearchParams({ subject_slug: subject, offset: String(offset), limit: "10" });
  if (topic) params.set("topic_slug", topic);
  return apiRequest<CatalogQuestionPage>(`/catalog/questions?${params}`);
};

export type ConversationItem = { id: string; title: string; updated_at: string };
export type SavedConversation = ConversationItem & { messages: Array<{
  id: string; role: "user" | "assistant"; content: string; citations: DoubtSource[];
  pyq_result: PyqResult | PaperSolutionResult | null; practice_result: PracticeResult | null;
}> };
export const getConversations = (token: string, offset = 0) => apiRequest<PageResult<ConversationItem>>(`/doubts/conversations?offset=${offset}&limit=20`, authorized(token));
export const getConversation = (token: string, id: string) => apiRequest<SavedConversation>(`/doubts/conversations/${id}`, authorized(token));

export const getProgressDashboard = (token: string) =>
  apiRequest<ProgressDashboard>("/progress/dashboard", authorized(token));

export const getPapers = (filters: { year?: number; cycle?: string; subject?: string } = {}) => {
  const params = new URLSearchParams();
  if (filters.year) params.set("year", String(filters.year));
  if (filters.cycle) params.set("cycle", filters.cycle);
  if (filters.subject) params.set("subject", filters.subject);
  const query = params.size ? `?${params.toString()}` : "";
  return paperListCache.get(query, () =>
    apiRequest<PaperListItem[]>(`/papers${query}`, { signal: AbortSignal.timeout(20_000) }));
};

export const getPaper = (token: string, paperId: string, signal?: AbortSignal) =>
  apiRequest<PaperDetail>(`/papers/${paperId}`, authorized(token, { signal }));

export const startPaperAttempt = (token: string, paperId: string, signal?: AbortSignal) =>
  apiRequest<PaperAttempt>(`/papers/${paperId}/attempts`, authorized(token, { method: "POST", signal }));

export const generatePaperExplanation = (token: string, paperId: string, questionId: string) =>
  apiRequest<PaperAIExplanation>(`/papers/${paperId}/questions/${questionId}/ai-explanation`, authorized(token, { method: "POST" }));

export const savePaperAnswer = (
  token: string,
  attemptId: string,
  questionId: string,
  input: { selected_index: number; marked_for_review: boolean; elapsed_seconds?: number },
) => apiRequest<PaperSavedAnswer>(
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

export const getPaperAttemptResult = (token: string, attemptId: string) =>
  apiRequest<PaperAttemptSummary>(
    `/paper-attempts/${attemptId}/result`,
    authorized(token),
  );

export const askDoubt = (
  token: string,
  input: {
    question: string;
    subject?: "general-knowledge" | "elementary-mathematics" | "english";
    conversation_id?: string;
    image?: DoubtImage;
    paper_question_id?: string;
  },
) => apiRequest<DoubtAnswer>(
  "/doubts/ask",
  authorized(token, { method: "POST", body: JSON.stringify(input) }),
);

export const getStudyProfile = (token: string) =>
  apiRequest<StudyProfile>("/doubts/personalization", authorized(token));
export const updateStudyProfile = (
  token: string, input: Partial<Pick<StudyProfile, "enabled" | "explanation_style">>,
) => apiRequest<StudyProfile>("/doubts/personalization", authorized(token, {
  method: "PATCH", body: JSON.stringify(input),
}));
export const clearStudyProfile = (token: string) =>
  apiRequest<StudyProfile>("/doubts/personalization", authorized(token, { method: "DELETE" }));
