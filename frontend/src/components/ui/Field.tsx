import React from "react";

export function Field({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <label className="ui-field">
      <span className="ui-label">{label}</span>
      {children}
    </label>
  );
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className = "", ...rest }, ref) {
    return <input ref={ref} className={`ui-input ${className}`.trim()} {...rest} />;
  }
);
