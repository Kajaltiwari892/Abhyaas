import assert from "node:assert/strict";
import test from "node:test";
import { autonomousAction, companionPose } from "../lib/companion-motion.ts";

test("automatic routine waves, reads, jumps and rests without buttons", () => {
  assert.equal(autonomousAction(1,false).action,"wave");
  assert.equal(autonomousAction(4,false).action,"idle");
  assert.equal(autonomousAction(8,false).action,"read");
  assert.equal(autonomousAction(14,false).action,"idle");
  const jump=autonomousAction(16.675,false);
  assert.equal(jump.action,"jump");
  assert.ok(companionPose(jump.elapsed,jump.action,false).lift>.5);
  assert.equal(autonomousAction(20,false).action,"idle");
  assert.deepEqual(autonomousAction(23,false),autonomousAction(1,false));
});

test("automatic actions are disabled for reduced motion", () => {
  for(const time of [1,8,16.675,23]) assert.equal(autonomousAction(time,true).action,"idle");
});

test("jump leaves the floor and lands", () => {
  assert.equal(companionPose(0,"jump",false).lift,0);
  assert.ok(companionPose(.675,"jump",false).lift>.5);
  assert.ok(companionPose(1.5,"jump",false).lift<.001);
});
test("reading actually turns a page and blinking closes the eyes", () => {
  assert.equal(companionPose(.5,"read",false).reading,true);
  assert.notEqual(companionPose(.2,"read",false).turnPage,companionPose(.8,"read",false).turnPage);
  assert.ok(companionPose(.13,"idle",false).blink<.1);
  assert.equal(companionPose(1,"idle",false).blink,1);
});
test("reduced motion keeps jumps and blinking static", () => {
  assert.equal(companionPose(.675,"jump",true).lift,0);
  assert.equal(companionPose(.13,"idle",true).blink,1);
  assert.equal(companionPose(.3,"read",true).turnPage,companionPose(.9,"read",true).turnPage);
});
