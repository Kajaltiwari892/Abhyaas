/** Describe elapsed waiting time, never fabricated generation progress. */
export function requestFeedback(elapsedSeconds: number, hasImage = false) {
  const seconds = Number.isFinite(elapsedSeconds) ? Math.max(0, Math.floor(elapsedSeconds)) : 0;
  return {
    label: seconds >= 12 ? "Still preparing your response" : hasImage ? "Reading your question image" : "Preparing your response",
    detail: seconds >= 60
      ? "Your request is still running. You do not need to send your question again."
      : seconds >= 12 ? "AI answers and large practice sets can take longer than paper lookups." : "",
    elapsed: seconds >= 12 ? `${seconds}s elapsed` : "",
  };
}
