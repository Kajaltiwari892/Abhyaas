import type { Metadata } from "next";
import AppShell from "../components/AppShell";
import ExamGuide from "./ExamGuide";

export const metadata: Metadata = {
  title: "CDS Exam Guide — Abhyaas",
  description: "Compare CDS academy routes, understand the written papers and follow the selection journey.",
};

export default function ExamInfoPage() {
  return <AppShell active="Exam info"><ExamGuide /></AppShell>;
}
