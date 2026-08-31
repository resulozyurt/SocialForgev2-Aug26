import React from "react";

export function Stats({ children }: { children: React.ReactNode }) {
  return <div className="ui-stats">{children}</div>;
}

export function Stat({
  label,
  value,
  delta,
  note,
}: {
  label: React.ReactNode;
  value: React.ReactNode;
  delta?: string;
  note?: React.ReactNode;
}) {
  return (
    <div className="ui-stat">
      <div className="lbl">{label}</div>
      <div className="val">
        {value}
        {delta ? <small>{delta}</small> : null}
      </div>
      {note ? <div className="note">{note}</div> : null}
    </div>
  );
}
