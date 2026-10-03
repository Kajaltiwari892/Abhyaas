export type AcademyTarget = "ima" | "ina" | "afa" | "ota";

const coreSubjects = [
  { slug: "english", name: "English" },
  { slug: "general-knowledge", name: "General Knowledge" },
] as const;
const allSubjects = [...coreSubjects, { slug: "elementary-mathematics", name: "Elementary Mathematics" }] as const;

const targets = {
  ima: { code: "IMA", name: "Indian Military Academy", subjects: allSubjects },
  ina: { code: "INA", name: "Indian Naval Academy", subjects: allSubjects },
  afa: { code: "AFA", name: "Air Force Academy", subjects: allSubjects },
  ota: { code: "OTA", name: "Officers Training Academy", subjects: coreSubjects },
} as const;

export function getPreparationTarget(value: unknown) {
  if (typeof value !== "string" || !Object.hasOwn(targets, value)) return null;
  return targets[value as AcademyTarget];
}

/** Recommendations only: keep other subjects reachable and never alter saved attempts. */
export function partitionPreparationSubjects<T extends { slug: string }>(subjects: T[], target: unknown) {
  const plan = getPreparationTarget(target);
  if (!plan) return { required: [...subjects], optional: [] as T[] };
  const requiredSlugs: readonly string[] = plan.subjects.map((subject) => subject.slug);
  return {
    required: subjects.filter((subject) => requiredSlugs.includes(subject.slug))
      .sort((a, b) => requiredSlugs.indexOf(a.slug) - requiredSlugs.indexOf(b.slug)),
    optional: subjects.filter((subject) => !requiredSlugs.includes(subject.slug)),
  };
}
