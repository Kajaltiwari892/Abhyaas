import { paperTextParts } from "@/lib/paper-text";

export default function PaperText({ value }: { value: string }) {
  return paperTextParts(value).map((part, index) => part.underline
    ? <u key={index}>{part.text}</u>
    : part.text);
}
