/** Date-only calendar arithmetic never depends on the browser's timezone. */
export function calendarCells(month: string): Array<string | null> {
  const [year, number] = month.split("-").map(Number);
  const first = new Date(Date.UTC(year, number - 1, 1));
  const length = new Date(Date.UTC(year, number, 0)).getUTCDate();
  const leading = (first.getUTCDay() + 6) % 7;
  return [...Array.from({length:leading},()=>null),...Array.from({length},(_,i)=>`${month}-${String(i+1).padStart(2,"0")}`)];
}
export function shiftMonth(month: string, by: number) {
  const [year, number] = month.split("-").map(Number);
  return new Date(Date.UTC(year, number - 1 + by, 1)).toISOString().slice(0,7);
}
export function roadmapDate(date: string, options: Intl.DateTimeFormatOptions = {day:"numeric",month:"short"}) {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString("en-IN",{...options,timeZone:"UTC"});
}
