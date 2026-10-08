export type StudySearchParams = Record<string, string | string[] | undefined>;

const first = (value: string | string[] | undefined) => Array.isArray(value) ? value[0] : value;

export function legacyPracticeDestination(params: StudySearchParams): string {
  const query = new URLSearchParams();
  if (first(params.view) === "notebook") {
    const revision = first(params.revision);
    if (revision) query.set("revision", revision);
    return `/mistake-notebook${query.size ? `?${query}` : ""}`;
  }

  for (const name of ["subject", "topic"] as const) {
    const value = first(params[name]);
    if (value) query.set(name, value);
  }
  if (first(params.view) === "history") query.set("view", "history");
  return `/subjects${query.size ? `?${query}` : ""}`;
}
