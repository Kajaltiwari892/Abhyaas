import test from "node:test";
import assert from "node:assert/strict";
import { createLatestSaveQueue } from "../lib/latest-save-queue.ts";
const deferred = () => { let resolve, reject; const promise = new Promise((yes,no) => {resolve=yes;reject=no;}); return {promise,resolve,reject}; };
const flush = async () => { for (let i=0;i<8;i++) await Promise.resolve(); };

test("slow saves coalesce to the latest complete snapshot, with no concurrent writes", async () => {
  const calls = [];
  const queue = createLatestSaveQueue(value => { const next=deferred(); calls.push({...next,value});return next.promise; });
  const first=queue.enqueue({answer:0}), second=queue.enqueue({answer:1}), last=queue.enqueue({answer:2});
  assert.equal(calls.length,1);
  calls[0].resolve(); await flush();
  assert.equal(calls.length,2); assert.deepEqual(calls[1].value,{answer:2});
  let settled=false; last.then(()=>{settled=true;}); await flush(); assert.equal(settled,false);
  calls[1].resolve(); await Promise.all([first,second,last,queue.drain()]);
});

test("a failed save keeps only the newest snapshot and retries on drain", async () => {
  const calls=[];
  const queue=createLatestSaveQueue(value=>{const next=deferred();calls.push({...next,value});return next.promise;});
  const failed=queue.enqueue(1);queue.enqueue(2).catch(()=>{});
  calls[0].reject(new Error("Offline")); await assert.rejects(failed,/Offline/);
  const retry=queue.drain(); assert.equal(calls[1].value,2);
  calls[1].resolve(); await retry;
  await queue.drain(); assert.equal(calls.length,2);
});

test("a write queued during settlement is included before drain resolves", async () => {
  let queue; const calls=[];
  queue=createLatestSaveQueue(async value=>{calls.push(value); if(value===1) queueMicrotask(()=>{void queue.enqueue(2);});});
  await queue.enqueue(1); assert.deepEqual(calls,[1,2]);
});
