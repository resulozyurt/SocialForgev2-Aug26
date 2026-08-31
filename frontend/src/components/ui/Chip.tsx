import React from "react";

export type SolutionKey =
  | "merchandising" | "field_audit" | "field_sales" | "home_service" | "ai" | "general";

const LABEL: Record<SolutionKey, string> = {
  merchandising: "Merchandising",
  field_audit: "Field Audit",
  field_sales: "Field Sales",
  home_service: "Home Service",
  ai: "AI",
  general: "General",
};

export function SolutionChip({ solution, label }: { solution: string; label?: string }) {
  const key = (solution in LABEL ? solution : "general") as SolutionKey;
  return <span className="ui-chip" data-sol={key}>{label ?? LABEL[key]}</span>;
}
