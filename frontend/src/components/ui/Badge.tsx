import React from "react";

type Tone = "neutral" | "ok" | "warn" | "bad" | "accent" | "muted";
const CLS: Record<Tone, string> = {
  neutral: "",
  ok: "ui-badge-ok",
  warn: "ui-badge-warn",
  bad: "ui-badge-bad",
  accent: "ui-badge-accent",
  muted: "ui-badge-muted",
};

export function Badge({
  tone = "neutral",
  dot = true,
  children,
}: {
  tone?: Tone;
  dot?: boolean;
  children: React.ReactNode;
}) {
  return <span className={["ui-badge", CLS[tone], dot ? "" : "plain"].filter(Boolean).join(" ")}>{children}</span>;
}
