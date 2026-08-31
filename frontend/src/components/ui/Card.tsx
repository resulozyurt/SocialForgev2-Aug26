import React from "react";

type DivProps = React.HTMLAttributes<HTMLDivElement>;

export function Card({ interactive, className = "", ...rest }: DivProps & { interactive?: boolean }) {
  return (
    <div
      className={["ui-card", interactive ? "interactive" : "", className].filter(Boolean).join(" ")}
      {...rest}
    />
  );
}

export function CardHead({ title, sub, right }: { title: React.ReactNode; sub?: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="ui-card-head">
      <h3>{title}</h3>
      {sub ? <span className="sub">{sub}</span> : null}
      {right ? <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>{right}</div> : null}
    </div>
  );
}

export function CardBody({ className = "", ...rest }: DivProps) {
  return <div className={`ui-card-body ${className}`.trim()} {...rest} />;
}

export function CardFoot({ className = "", ...rest }: DivProps) {
  return <div className={`ui-card-foot ${className}`.trim()} {...rest} />;
}
