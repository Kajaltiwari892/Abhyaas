export type CompanionAction = "wave" | "read" | "jump";

/** A quiet repeating routine; elapsed is visible time, so hidden tabs do not skip actions. */
export function autonomousAction(elapsed: number, reduced: boolean): {
  action: CompanionAction | "idle"; elapsed: number;
} {
  if (reduced) return { action: "idle", elapsed: 0 };
  const time = Math.max(0, elapsed) % 22;
  if (time < 2.8) return { action: "wave", elapsed: time };
  if (time < 6) return { action: "idle", elapsed: time - 2.8 };
  if (time < 12) return { action: "read", elapsed: time - 6 };
  if (time < 16) return { action: "idle", elapsed: time - 12 };
  if (time < 17.6) return { action: "jump", elapsed: time - 16 };
  return { action: "idle", elapsed: time - 17.6 };
}

/** Pure animation timing, kept separate from WebGL so motion can be regression-tested. */
export function companionPose(elapsed: number, action: CompanionAction | "idle", reduced: boolean) {
  const time = Math.max(0, elapsed);
  const jumpProgress = Math.min(time / 1.35, 1);
  const lift = action === "jump" && !reduced ? Math.sin(jumpProgress * Math.PI) * .55 : 0;
  const blinkPhase = time % 4.8;
  const blink = reduced ? 1 : blinkPhase < .26 ? Math.max(.08, Math.abs(blinkPhase - .13) / .13) : 1;
  return {
    lift, blink,
    reading: action === "read",
    turnPage: action === "read" && !reduced ? Math.min(1, (time % 2.8) / 1.3) * Math.PI : .4,
    wave: action === "wave" && !reduced ? -2.1 + Math.sin(time * 8) * .38 : -.3,
    squash: action === "jump" && !reduced ? 1 - Math.sin(jumpProgress * Math.PI * 2) * .08 : 1,
  };
}
