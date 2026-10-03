export function solutionLabel(status: string): string {
  switch (status) {
    case "verified": return "Verified key · explanation may be AI-generated";
    case "ai": return "AI solution · official verification pending";
    case "key_conflict": return "Verified key · explanation needs review";
    case "key_pending": return "Verified answer key unavailable";
    case "needs_source": return "Source material needed";
    default: return "Uncertain · needs review";
  }
}

export function solutionContinuation(next: number, end: number): string {
  return `Continue · Q${next}–${Math.min(next + 9, end)}`;
}
