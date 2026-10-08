import assert from "node:assert/strict";
import test from "node:test";
import { calendarCells, shiftMonth, roadmapDate } from "../lib/roadmap-calendar.ts";

test("calendar aligns Monday-first weeks and handles leap days",()=>{
  const october=calendarCells("2026-10");
  assert.deepEqual(october.slice(0,4),[null,null,null,"2026-10-01"]);
  assert.equal(october.at(-1),"2026-10-31");
  assert.equal(calendarCells("2028-02").filter(Boolean).length,29);
  assert.equal(calendarCells("2027-02").filter(Boolean).length,28);
});
test("month navigation and date labels do not shift across years or timezones",()=>{
  assert.equal(shiftMonth("2026-12",1),"2027-01");
  assert.equal(shiftMonth("2027-01",-1),"2026-12");
  assert.equal(roadmapDate("2027-02-11"),"11 Feb");
});
