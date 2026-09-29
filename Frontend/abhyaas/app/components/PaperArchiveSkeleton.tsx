export default function PaperArchiveSkeleton() {
  return <div className="paper-archive-skeleton" role="status" aria-label="Loading official papers"><span>Loading your paper archive…</span><div>{[0,1,2].map(key=><article key={key} aria-hidden="true"><i/><i/><i/><i/></article>)}</div></div>;
}
