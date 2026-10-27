import type { Step } from "../types";

const ICON: Record<Step["status"], string> = {
  ok: "✓",
  error: "✕",
  skipped: "–",
};

export function StepTimeline({ steps }: { steps: Step[] }) {
  return (
    <ol className="steps">
      {steps.map((step, i) => (
        <li key={`${step.name}-${i}`} className={`step step-${step.status}`} title={step.detail}>
          <span className="step-icon">{ICON[step.status]}</span>
          <span className="step-name">{step.name}</span>
          {step.ms > 0 && <span className="step-ms">{step.ms}ms</span>}
        </li>
      ))}
    </ol>
  );
}