import AppShell from "../components/AppShell";
import PracticeQuestionSkeleton from "../practice/PracticeQuestionSkeleton";
import s from "../practice/practice.module.css";

export default function LoadingSubjects() {
  return <AppShell active="Subjects"><main className={`${s.workspace} ${s.live}`}><header className={s.header}><h1>Subjects</h1></header><PracticeQuestionSkeleton /></main></AppShell>;
}
