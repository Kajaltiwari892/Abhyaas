// Preserve source underlining without interpreting arbitrary HTML or Markdown.
export function paperTextParts(text: string) {
  const parts: { text: string; underline: boolean }[] = [];
  const pattern = /(?<![\w_])_([^_\n]*[A-Za-z][^_\n]*)_(?![\w_])/g;
  let offset = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > offset) parts.push({ text: text.slice(offset, match.index), underline: false });
    parts.push({ text: match[1], underline: true });
    offset = match.index + match[0].length;
  }
  if (offset < text.length) parts.push({ text: text.slice(offset), underline: false });
  return parts;
}
