type ArchiveEntry = { year: number; cycle: string; subject_slug: string };

export function paperArchiveYears(papers: ArchiveEntry[]) {
  return [...new Set(papers.map(paper => paper.year))].sort((a, b) => b - a);
}

export function filterPaperArchive<T extends ArchiveEntry>(
  papers: T[],
  filters: { year: string; cycle: string; subject: string },
) {
  return papers.filter(paper =>
    (!filters.year || paper.year === Number(filters.year)) &&
    (!filters.cycle || paper.cycle === filters.cycle) &&
    (!filters.subject || paper.subject_slug === filters.subject),
  );
}

export function paperAvailability(paper: {
  available_question_count: number;
  official_question_count: number;
}) {
  if (!paper.available_question_count) return "pdf";
  return paper.available_question_count >= paper.official_question_count ? "interactive" : "partial";
}
