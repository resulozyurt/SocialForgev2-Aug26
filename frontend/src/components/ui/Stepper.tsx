import React from "react";

export type StepState = "done" | "active" | "todo";
export type StepItem = { key: string; label: React.ReactNode; sub?: React.ReactNode; state: StepState };

function Arrow() {
  return (
    <svg className="arrow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}

export function Stepper({
  items,
  current,
  onSelect,
}: {
  items: StepItem[];
  current?: string;
  onSelect?: (key: string) => void;
}) {
  return (
    <div className="ui-stepper">
      {items.map((s, i) => {
        const inner = (
          <>
            <span className="ico">{s.state === "done" ? "✓" : i + 1}</span>
            <span className="txt">
              <b>{s.label}</b>
              {s.sub ? <span>{s.sub}</span> : null}
            </span>
            {i < items.length - 1 ? <Arrow /> : null}
          </>
        );
        const common = {
          className: "ui-step",
          "data-state": s.state,
          "aria-current": current === s.key,
        } as const;
        return onSelect ? (
          <button key={s.key} {...common} onClick={() => onSelect(s.key)}>
            {inner}
          </button>
        ) : (
          <div key={s.key} {...common}>
            {inner}
          </div>
        );
      })}
    </div>
  );
}
