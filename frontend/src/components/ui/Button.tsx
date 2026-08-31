import React from "react";

type Variant = "primary" | "ghost" | "subtle" | "danger";
type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: "sm" | "md";
};

export function Button({ variant = "ghost", size = "md", className = "", ...rest }: Props) {
  const cls = [
    "ui-btn",
    `ui-btn-${variant}`,
    size === "sm" ? "ui-btn-sm" : "",
    className,
  ].filter(Boolean).join(" ");
  return <button className={cls} {...rest} />;
}
