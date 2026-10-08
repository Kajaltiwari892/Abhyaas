type Answer = { correct_index: number | null; is_scorable?: boolean; is_verified?: boolean };

export function hasStoredAnswer(answer: Answer | undefined): boolean {
  return Boolean(answer && (answer.is_scorable ?? answer.is_verified) && Number.isInteger(answer.correct_index));
}

export function paperScoreDescription(result: { scored_questions: number; total_questions: number; unscored_questions: number; score_basis: string }): string {
  if (!result.scored_questions) return "Your answers are saved. The answers for this paper still need checking.";
  const label = result.score_basis === "official" ? "Score" : "Practice score";
  return `${label} based on ${result.scored_questions} of ${result.total_questions} questions.${result.unscored_questions ? ` ${result.unscored_questions} not included yet.` : ""}`;
}
