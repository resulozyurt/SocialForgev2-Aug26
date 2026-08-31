import React from "react";

const HEX = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

export function ColorField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const picker = HEX.test(value) ? value : "#000000";
  return (
    <div className="ui-field">
      <span className="ui-label">{label}</span>
      <div className="ui-colorfield">
        <input
          type="color"
          className="ui-colorswatch"
          value={picker}
          onChange={(e) => onChange(e.target.value)}
          aria-label={`${label} picker`}
        />
        <input
          className="ui-input"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          spellCheck={false}
        />
      </div>
    </div>
  );
}
