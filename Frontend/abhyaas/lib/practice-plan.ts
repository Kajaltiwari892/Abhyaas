export type PracticeMode = "fresh" | "mixed" | "similar";
type Availability = { total: number; unseen: number };

export function practiceSetSize(mode: PracticeMode, requested: number, pool?: Availability): number {
  if (mode === "similar") return Math.min(requested, 50);
  return Math.min(requested, pool ? mode === "fresh" ? pool.unseen : pool.total : 0);
}

export function practiceChoices(mode: PracticeMode): number[] {
  return mode === "similar" ? [10, 25, 50] : [10, 25, 50, 100, 120];
}
