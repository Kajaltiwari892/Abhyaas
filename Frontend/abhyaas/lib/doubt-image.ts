import type { DoubtImage } from "./study-api";

export type QuestionAttachment = DoubtImage & { name: string; preview: string };

export async function readQuestionImage(file: File): Promise<QuestionAttachment> {
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
    throw new Error("Use a JPG, PNG or WebP image. PDFs and other files are not supported.");
  }
  if (!file.size || file.size > 4 * 1024 * 1024) throw new Error("Choose an image no larger than 4 MB.");
  const preview = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("This image could not be opened. Try another file."));
    reader.readAsDataURL(file);
  });
  await new Promise<void>((resolve, reject) => {
    const picture = new window.Image();
    picture.onload = () => {
      if (picture.width * picture.height > 12_000_000 || Math.max(picture.width, picture.height) > 6000) {
        reject(new Error("Use an image under 12 megapixels and 6000 pixels per side."));
      } else if (Math.min(picture.width, picture.height) < 16) {
        reject(new Error("This image is too small. Try a clearer screenshot."));
      } else resolve();
    };
    picture.onerror = () => reject(new Error("This image is damaged or unsupported."));
    picture.src = preview;
  });
  return { name: file.name || "Pasted question", preview, mime_type: file.type as DoubtImage["mime_type"], data: preview.split(",")[1] };
}
