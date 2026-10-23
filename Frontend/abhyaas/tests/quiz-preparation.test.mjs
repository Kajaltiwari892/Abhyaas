import test from "node:test";
import assert from "node:assert/strict";
import { queryHarness, ApiError } from "./helpers/query-harness.mjs";
function apiHost(step) {
  const host = queryHarness((path, init, count) => step(count), {setTimeout: fn => setTimeout(fn, 0), clearTimeout});
  return { ...host, api: host.api("study-plan-api") };
}
const preparing=n=>({status:"preparing",prepared_count:n,total:50,retry_after_ms:0,attempt:null});
const ready={status:"ready",prepared_count:50,total:50,attempt:{id:"quiz",questions:Array(50).fill({})}};

test("short preparation steps report actual counts and return only the complete saved quiz",async()=>{
  const host=apiHost(i=>i<4?preparing(i*10):ready),counts=[];
  const result=await host.api.startDailyQuiz("token","task/one",undefined,n=>counts.push(n));
  assert.equal(result.id,"quiz"); assert.deepEqual(counts,[10,20,30]);
  assert.ok(host.calls.every(call=>call.path==="/study-plan/tasks/task%2Fone/quiz/prepare"));
  assert.ok(host.calls.every(call=>call.init.method==="POST"));
});
test("a lost response is safely retried on the same durable preparation endpoint",async()=>{
  const host=apiHost(i=>{if(i===1)throw new ApiError("Offline",0);return ready;});
  assert.equal((await host.api.startDailyQuiz("token","task")).id,"quiz");
  assert.equal(host.calls.length,2);
});
test("cancellation and account changes cannot continue preparation under an old session",async()=>{
  const abort=new AbortController(),host=apiHost(()=>preparing(20));
  await assert.rejects(host.api.startDailyQuiz("token","task",abort.signal,()=>abort.abort()),{name:"AbortError"});
  assert.equal(host.calls.length,1);
  const other=apiHost(()=>preparing(20));
  await assert.rejects(other.api.startDailyQuiz("token","task",undefined,()=>other.controller.endSession()),/session has changed/);
  assert.equal(other.calls.length,1);
});
test("provider failures and malformed progress stop with retryable UI, never fabricated questions",async()=>{
  const unavailable=apiHost(()=>{throw new ApiError("Prepared questions are saved",503);});
  await assert.rejects(unavailable.api.startDailyQuiz("token","task"),/saved/);
  assert.equal(unavailable.calls.length,1);
  const malformed=apiHost(()=>({...preparing(60)}));
  await assert.rejects(malformed.api.startDailyQuiz("token","task"),/couldn't be opened/);
});
