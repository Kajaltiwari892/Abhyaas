import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const layout = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");

test("the existing font variables use bundled fonts, never a Google download at build time", () => {
  assert.match(layout, /from "next\/font\/local"/);
  assert.doesNotMatch(layout, /next\/font\/google/);
  for (const variable of ["--font-geist-sans", "--font-geist-mono"]) {
    assert.ok(layout.includes(`variable: "${variable}"`));
  }
  assert.ok(layout.includes("geistSans.variable"));
  assert.ok(layout.includes("geistMono.variable"));
  assert.equal((layout.match(/adjustFontFallback: false/g) || []).length, 2);
});

test("both variable font files are real WOFF2 assets with the redistribution license", () => {
  for (const name of ["geist-latin-variable.woff2", "geist-mono-latin-variable.woff2"]) {
    const font = readFileSync(new URL(`../app/fonts/${name}`, import.meta.url));
    assert.equal(font.toString("ascii", 0, 4), "wOF2");
    assert.equal(font.readUInt32BE(8), font.length);
    assert.ok(font.length > 10_000);
    assert.ok(layout.includes(`./fonts/${name}`));
  }
  const license = readFileSync(new URL("../app/fonts/OFL.txt", import.meta.url), "utf8");
  assert.match(license, /SIL OPEN FONT LICENSE Version 1\.1/);
});
