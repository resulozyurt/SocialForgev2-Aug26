import React from "react";

export type TabItem = { key: string; label: React.ReactNode; count?: number };

export function Tabs({
  items,
  active,
  onChange,
}: {
  items: TabItem[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="ui-tabs" role="tablist">
      {items.map((it) => (
        <button
          key={it.key}
          role="tab"
          aria-selected={active === it.key}
          className={`ui-tab${active === it.key ? " active" : ""}`}
          onClick={() => onChange(it.key)}
        >
          {it.label}
          {it.count != null ? <span className="ui-tab-count">{it.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
