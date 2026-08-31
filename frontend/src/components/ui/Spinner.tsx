import React from "react";

export function Spinner({ size = 18 }: { size?: number }) {
  return <span className="ui-spinner" style={{ width: size, height: size }} aria-hidden="true" />;
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="ui-loading" role="status" aria-live="polite">
      <Spinner />
      <span>{label}</span>
    </div>
  );
}
