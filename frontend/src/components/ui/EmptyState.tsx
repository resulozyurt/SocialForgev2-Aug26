import React from "react";

export function EmptyState({ title, children }: { title: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="ui-empty">
      <h4>{title}</h4>
      {children ? <div>{children}</div> : null}
    </div>
  );
}
