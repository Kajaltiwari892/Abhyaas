import { redirect } from "next/navigation";
import { legacyPracticeDestination, type StudySearchParams } from "@/lib/study-navigation";

// Keep bookmarks and older shared links working without a second practice page.
export default async function PracticePage({ searchParams }: { searchParams: Promise<StudySearchParams> }) {
  redirect(legacyPracticeDestination(await searchParams));
}
