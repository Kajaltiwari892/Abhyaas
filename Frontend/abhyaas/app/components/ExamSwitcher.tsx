import { Check, ChevronDown, LockKeyhole, Shield } from "lucide-react";

const upcomingExams = [
  { name: "NEET", description: "Medical entrance" },
  { name: "JEE", description: "Engineering entrance" },
  { name: "UPSC CSE", description: "Civil services" },
];

export default function ExamSwitcher({ compact = false }: { compact?: boolean }) {
  return (
    <details className={`exam-switcher ${compact ? "compact" : ""}`}>
      <summary aria-label="Choose an exam">
        <span className="exam-shield"><Shield size={14} /></span>
        <span className="exam-current"><small>Preparing for</small><strong>CDS</strong></span>
        <ChevronDown className="exam-chevron" size={15} />
      </summary>
      <div className="exam-menu">
        <span className="exam-menu-label">Choose your exam</span>
        <div className="exam-option selected">
          <span className="exam-option-icon"><Shield size={16} /></span>
          <span><strong>CDS</strong><small>Defence services</small></span>
          <Check size={15} />
        </div>
        {upcomingExams.map((exam) => (
          <div className="exam-option disabled" key={exam.name} aria-disabled="true">
            <span className="exam-option-icon"><LockKeyhole size={14} /></span>
            <span><strong>{exam.name}</strong><small>{exam.description}</small></span>
            <em>Coming soon</em>
          </div>
        ))}
        <p>Abhyaas is currently focused entirely on CDS preparation.</p>
      </div>
    </details>
  );
}
