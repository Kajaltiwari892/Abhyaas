import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { footerWordmarkPath } from "../lib/footer-wordmark.ts";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("footer uses real glyph outlines and text-only hover targeting", () => {
  assert.match(footerWordmarkPath, /^M/);
  assert.ok(!/NaN|undefined/.test(footerWordmarkPath));
  const css = read("../app/globals.css");
  assert.ok(!css.includes(".footer-wordmark:hover"));
  assert.ok(css.includes(":has(.footer-word-outline:hover)"));
  assert.ok(css.includes(".footer-wordmark:focus-visible"));
  assert.match(read("../app/page.tsx"), /<path className="footer-word-outline" d=\{footerWordmarkPath\}/);
});

test("chat rail remains mounted, has hidden-focus protection and motion preferences", () => {
  const component = read("../app/doubt-solver/ChatHistory.tsx");
  assert.ok(!component.includes("if (!open) return null"));
  assert.ok(component.includes("inert={!open}"));
  assert.ok(component.includes('event.key === "Escape"'));
  const css = read("../app/doubt-solver/chat-history.module.css");
  assert.ok(css.includes("prefers-reduced-motion:reduce"));
  assert.ok(css.includes('data-open="true"'));
  assert.ok(css.includes("transition:width"));
});
