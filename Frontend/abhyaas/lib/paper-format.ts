const LATEX_WORDS: Record<string, string> = {
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", lambda: "λ", pi: "π", theta: "θ",
  times: "×", cdot: "·", dots: "…", circ: "°", neq: "≠", ne: "≠", le: "≤", ge: "≥",
  pm: "±", angle: "∠", tan: "tan", cot: "cot", sin: "sin", cos: "cos", sec: "sec",
  csc: "cosec", quad: " ", displaystyle: "", left: "", right: "",
};
const SUPERSCRIPT_DIGITS: Record<string, string> = { "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻" };

function bracedGroup(text: string, opening: number) {
  if (text[opening] !== "{") return null;
  let depth = 0;
  for (let index = opening; index < text.length; index += 1) {
    if (text[index] === "{") depth += 1;
    if (text[index] === "}") depth -= 1;
    if (depth === 0) return { value: text.slice(opening + 1, index), end: index + 1 };
  }
  return null;
}

function replaceLatexGroups(text: string, command: "frac" | "sqrt") {
  const marker = `\\${command}{`;
  let result = text;
  let start = result.indexOf(marker);
  while (start >= 0) {
    const first = bracedGroup(result, start + marker.length - 1);
    if (!first) break;
    if (command === "sqrt") {
      result = `${result.slice(0, start)}√(${first.value})${result.slice(first.end)}`;
    } else {
      const second = bracedGroup(result, first.end);
      if (!second) break;
      result = `${result.slice(0, start)}(${first.value})/(${second.value})${result.slice(second.end)}`;
    }
    start = result.indexOf(marker, start + 1);
  }
  return result;
}

export function formatPaperText(value: string, trim = true) {
  let text = value.replace(/\$/g, "");
  for (let pass = 0; pass < 4; pass += 1) {
    text = replaceLatexGroups(replaceLatexGroups(text, "frac"), "sqrt");
  }
  text = text
    .replace(/\\text\{([^{}]*)\}/g, "$1")
    .replace(/\^\{(-?\d+)\}/g, (_, digits: string) => [...digits].map(digit => SUPERSCRIPT_DIGITS[digit] ?? digit).join(""))
    .replace(/\^\{([^{}]+)\}/g, "^($1)")
    .replace(/_\{([^{}]+)\}/g, "_($1)")
    .replace(/\\([A-Za-z]+)/g, (_, word: string) => LATEX_WORDS[word] ?? word)
    .replace(/\\([()[\]])/g, "$1")
    .replace(/\\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n");
  return trim ? text.trim() : text;
}
