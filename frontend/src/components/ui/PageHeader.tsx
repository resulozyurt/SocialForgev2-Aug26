import React from "react";

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="ui-pagehead">
      <div className="grow">
        {eyebrow ? <p className="ui-eyebrow">{eyebrow}</p> : null}
        <h1 className="ui-title">{title}</h1>
        {subtitle ? <p className="ui-subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="ui-actions">{actions}</div> : null}
    </div>
  );
}
