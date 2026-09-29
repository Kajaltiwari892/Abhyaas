import AppShell from "../components/AppShell";
import PaperArchiveSkeleton from "../components/PaperArchiveSkeleton";
export default function LoadingPapers() {
  return <AppShell active="Previous papers"><main className="workspace papers-workspace"><header className="workspace-header"><div><span className="workspace-kicker">Learn from the real examination</span><h1>Previous papers</h1><p>Opening the official paper archive.</p></div></header><PaperArchiveSkeleton/></main></AppShell>;
}
