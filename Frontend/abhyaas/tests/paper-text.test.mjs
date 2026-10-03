import assert from "node:assert/strict";
import test from "node:test";
import { paperTextParts } from "../lib/paper-text.ts";

test("English source underlining is preserved", () => {
  assert.deepEqual(paperTextParts("The views were _equivocal_."), [
    { text: "The views were ", underline: false },
    { text: "equivocal", underline: true },
    { text: ".", underline: false },
  ]);
});

test("blanks, subscripts and HTML-like source text remain literal", () => {
  const text = "Fill __________. x_1 + x_2. <script>not executable</script>";
  assert.deepEqual(paperTextParts(text), [{ text, underline: false }]);
});
