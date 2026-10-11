import { formatPaperText } from "@/lib/paper-format";
import { paperTextParts } from "@/lib/paper-text";

// Render only supported underline notation. All other content stays plain text.
export default function NotebookText({ text }: { text: string }) {
  const value = text.replace(/\\underline\{([^{}]+)\}/g, "<u>$1</u>");
  return <>{value.split(/(<u>[\s\S]*?<\/u>)/g).map((part, i) => part.startsWith("<u>") && part.endsWith("</u>") ? <u key={i}>{formatPaperText(part.slice(3, -4), false)}</u> : <span key={i}>{paperTextParts(formatPaperText(part, false)).map((piece, j) => piece.underline ? <u key={j}>{piece.text}</u> : piece.text)}</span>)}</>;
}
