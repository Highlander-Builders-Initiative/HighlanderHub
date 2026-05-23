"use client";

import { useRef, useState, type ChangeEvent, type ReactNode } from "react";

export function FormSection({
  eyebrow,
  first = false,
  children,
}: {
  eyebrow?: string;
  first?: boolean;
  children: ReactNode;
}) {
  return (
    <section className={first ? "" : "mt-10"}>
      {!first && <div className="hairline mb-6" />}
      {eyebrow && <p className="mb-4 text-[13px] text-muted">{eyebrow}</p>}
      <div className="space-y-6">{children}</div>
    </section>
  );
}

export function Field({
  label,
  name,
  type = "text",
  required = false,
  optional = false,
  maxLength,
  placeholder,
  error,
  showCounter = false,
  autoGrow = false,
  rows = 3,
}: {
  label: string;
  name: string;
  type?: string;
  required?: boolean;
  optional?: boolean;
  maxLength?: number;
  placeholder?: string;
  error?: string;
  showCounter?: boolean;
  autoGrow?: boolean;
  rows?: number;
}) {
  const [length, setLength] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const errorId = `${name}-error`;
  const describedBy = error ? errorId : undefined;
  const baseClass =
    "interactive-focus mt-1 w-full rounded-md border border-ink/15 bg-canvas px-3 py-2 text-ink placeholder:text-muted/70 focus:border-ink";
  const inputClass = error
    ? `${baseClass} border-deep-coral focus:border-deep-coral`
    : baseClass;

  function handleChange(
    e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) {
    if (showCounter) setLength(e.target.value.length);
    if (autoGrow && textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }

  const counterAtRisk =
    maxLength != null && length >= Math.floor(maxLength * 0.8);

  return (
    <label className="block">
      <span className="flex items-center justify-between gap-3 text-sm font-medium text-ink/80">
        <span>{label}</span>
        {showCounter && maxLength != null ? (
          <span
            className={`text-xs font-normal tabular-nums ${
              counterAtRisk ? "text-deep-coral" : "text-muted"
            }`}
            aria-live="polite"
          >
            {length}/{maxLength}
          </span>
        ) : optional ? (
          <span className="text-xs font-normal text-muted">Optional</span>
        ) : null}
      </span>
      {type === "textarea" ? (
        <textarea
          ref={textareaRef}
          name={name}
          required={required}
          maxLength={maxLength}
          placeholder={placeholder}
          rows={rows}
          onChange={showCounter || autoGrow ? handleChange : undefined}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy || undefined}
          className={`${inputClass} ${autoGrow ? "resize-none overflow-hidden" : ""}`}
        />
      ) : (
        <input
          name={name}
          type={type}
          required={required}
          maxLength={maxLength}
          placeholder={placeholder}
          onChange={showCounter ? handleChange : undefined}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy || undefined}
          className={inputClass}
        />
      )}
      {error && (
        <p id={errorId} className="mt-1 text-sm text-deep-coral">
          {error}
        </p>
      )}
    </label>
  );
}

export function SelectField({
  label,
  name,
  options,
}: {
  label: string;
  name: string;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-ink/80">{label}</span>
      <select
        name={name}
        defaultValue="club"
        className="interactive-focus mt-1 w-full rounded-md border border-ink/15 bg-canvas px-3 py-2 text-ink focus:border-ink"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Checkbox({
  label,
  name,
  defaultChecked = false,
  onChange,
}: {
  label: string;
  name: string;
  defaultChecked?: boolean;
  onChange?: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-ink/80">
      <input
        type="checkbox"
        name={name}
        defaultChecked={defaultChecked}
        onChange={onChange ? (e) => onChange(e.target.checked) : undefined}
        className="interactive-focus h-4 w-4 rounded border-ink/15 text-ink"
      />
      {label}
    </label>
  );
}

export function Chip({
  active,
  disabled,
  onClick,
  children,
}: {
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  const base =
    "interactive-focus rounded-full px-3 py-1.5 text-xs font-medium transition-colors duration-150";
  const tone = active
    ? "border border-ink bg-ink text-canvas"
    : "border border-ink/15 bg-canvas text-ink/80 hover:border-ink/30 hover:text-ink";
  const state = disabled
    ? "cursor-not-allowed opacity-50 hover:border-ink/15 hover:text-ink/80"
    : "";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      disabled={disabled}
      className={`${base} ${tone} ${state}`}
    >
      {children}
    </button>
  );
}
