"use client";

import { useEffect, useState, useRef } from "react";
import { supabase } from "@/lib/supabase";
import { track } from "@/lib/analytics";
import { normalizeHttpUrl, validateEventTimes } from "@/lib/event-validation";
import type { EventCategory } from "@/types/event";

const CATEGORIES: { value: EventCategory; label: string }[] = [
  { value: "club", label: "Club / org" },
  { value: "academic", label: "Academic / lecture" },
  { value: "social", label: "Social" },
  { value: "career", label: "Career / professional" },
  { value: "sports", label: "Sports / athletics" },
  { value: "arts", label: "Arts / performance" },
  { value: "community", label: "Community / service" },
  { value: "free_food", label: "Free food" },
];

type Status =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "success" }
  | { kind: "error"; message: string };

type FieldName =
  | "title"
  | "starts_at"
  | "ends_at"
  | "location"
  | "host"
  | "source_url"
  | "image_url"
  | "rsvp_url"
  | "submitter_name"
  | "submitter_email";

const REQUIRED_FIELDS: FieldName[] = [
  "title",
  "starts_at",
  "location",
  "host",
  "submitter_name",
  "submitter_email",
];

type FieldErrors = Partial<Record<FieldName, string>>;

const OPTIONAL_URL_FIELDS: FieldName[] = ["source_url", "image_url", "rsvp_url"];
const URL_ERROR = "Use an http(s) URL.";

function validateRequiredFields(form: FormData): FieldErrors {
  return REQUIRED_FIELDS.reduce<FieldErrors>((errors, field) => {
    if (!String(form.get(field) ?? "").trim()) {
      errors[field] = "This field is required.";
    }
    return errors;
  }, {});
}

function validateOptionalUrlFields(form: FormData): FieldErrors {
  return OPTIONAL_URL_FIELDS.reduce<FieldErrors>((errors, field) => {
    const value = String(form.get(field) ?? "").trim();
    if (value && !normalizeHttpUrl(value)) {
      errors[field] = URL_ERROR;
    }
    return errors;
  }, {});
}

export default function SubmitForm() {
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [isImageUrlOpen, setIsImageUrlOpen] = useState(false);
  const startedRef = useRef(false);

  useEffect(() => {
    track("submit_page_view", {});
  }, []);

  useEffect(() => {
    if (fieldErrors.image_url) setIsImageUrlOpen(true);
  }, [fieldErrors.image_url]);

  function onFirstInteract() {
    if (startedRef.current) return;
    startedRef.current = true;
    track("submission_start", {});
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const form = new FormData(e.currentTarget);
    const timeValidation = validateEventTimes(
      form.get("starts_at"),
      form.get("ends_at")
    );
    const nextFieldErrors = {
      ...validateRequiredFields(form),
      ...validateOptionalUrlFields(form),
    };

    if (
      timeValidation.error &&
      timeValidation.field &&
      !nextFieldErrors[timeValidation.field]
    ) {
      nextFieldErrors[timeValidation.field] = timeValidation.error;
    }

    if (Object.keys(nextFieldErrors).length > 0) {
      setFieldErrors(nextFieldErrors);
      setStatus({ kind: "idle" });
      return;
    }

    if (!timeValidation.startsAt) {
      setFieldErrors({ starts_at: "Start time is invalid." });
      setStatus({ kind: "idle" });
      return;
    }

    setFieldErrors({});
    setStatus({ kind: "submitting" });

    const tagsRaw = (form.get("tags") as string) || "";
    const sourceUrl = normalizeHttpUrl(form.get("source_url"));
    const imageUrl = normalizeHttpUrl(form.get("image_url"));
    const rsvpUrl = normalizeHttpUrl(form.get("rsvp_url"));

    const row = {
      title: form.get("title") as string,
      description: (form.get("description") as string) || "",
      starts_at: timeValidation.startsAt,
      ends_at: timeValidation.endsAt,
      location: form.get("location") as string,
      host: form.get("host") as string,
      category: form.get("category") as EventCategory,
      tags: tagsRaw
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      source_url: sourceUrl,
      image_url: imageUrl,
      is_free: form.get("is_free") === "on",
      rsvp_required: form.get("rsvp_required") === "on",
      rsvp_url: rsvpUrl,
      submitter_name: form.get("submitter_name") as string,
      submitter_email: form.get("submitter_email") as string,
      submitter_org: (form.get("submitter_org") as string) || null,
    };

    const { error } = await supabase.from("submissions").insert(row);

    if (error) {
      track("submission_error", { message: error.message });
      setStatus({ kind: "error", message: error.message });
      return;
    }
    track("submission_complete", {});
    setStatus({ kind: "success" });
  }

  if (status.kind === "success") {
    return (
      <div className="rounded-lg border border-deep-leaf/30 bg-leaf/10 p-6">
        <h2 className="font-display text-2xl">Got it.</h2>
        <p className="mt-2 text-ink/80">
          Your event is queued for review. You&apos;ll see it on the bulletin
          once it&apos;s approved, usually within a day.
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      onFocusCapture={onFirstInteract}
      onChange={onFirstInteract}
    >
      <FormSection first>
        <FlyerPlaceholder
          isOpen={isImageUrlOpen}
          onToggle={() => setIsImageUrlOpen((v) => !v)}
        />
        <div id="image-url-field" className={isImageUrlOpen ? "mt-4" : "hidden"}>
          <Field
            label="Image URL"
            name="image_url"
            type="url"
            placeholder="https://..."
            error={fieldErrors.image_url}
          />
        </div>
      </FormSection>

      <FormSection eyebrow="the event">
        <Field
          label="Event title"
          name="title"
          required
          maxLength={200}
          error={fieldErrors.title}
        />
        <Field
          label="Description"
          name="description"
          type="textarea"
          placeholder="A sentence or two: what's happening, who's it for?"
        />
        <SelectField label="Category" name="category" options={CATEGORIES} />
        <Field
          label="Tags (comma-separated)"
          name="tags"
          placeholder="cs, networking, free pizza"
        />
      </FormSection>

      <FormSection eyebrow="when and where">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <Field
            label="Starts"
            name="starts_at"
            type="datetime-local"
            required
            error={fieldErrors.starts_at}
          />
          <Field
            label="Ends (optional)"
            name="ends_at"
            type="datetime-local"
            error={fieldErrors.ends_at}
          />
        </div>
        <Field
          label="Location"
          name="location"
          required
          placeholder="HUB 302, or 'Bell Tower lawn'"
          error={fieldErrors.location}
        />
        <Field
          label="Host / organization"
          name="host"
          required
          placeholder="ACM at UCR"
          error={fieldErrors.host}
        />
      </FormSection>

      <FormSection eyebrow="links and tickets">
        <Field
          label="Event page or flyer URL (optional)"
          name="source_url"
          type="url"
          error={fieldErrors.source_url}
        />
        <div className="flex gap-6">
          <Checkbox label="Free to attend" name="is_free" defaultChecked />
          <Checkbox label="RSVP required" name="rsvp_required" />
        </div>
        <Field
          label="RSVP / ticket URL (if required)"
          name="rsvp_url"
          type="url"
          error={fieldErrors.rsvp_url}
        />
      </FormSection>

      <FormSection eyebrow="you">
        <Field
          label="Your name"
          name="submitter_name"
          required
          error={fieldErrors.submitter_name}
        />
        <Field
          label="Your email"
          name="submitter_email"
          type="email"
          required
          error={fieldErrors.submitter_email}
        />
        <Field
          label="Org affiliation (optional)"
          name="submitter_org"
          placeholder="ACM at UCR"
        />
      </FormSection>

      <button
        type="submit"
        disabled={status.kind === "submitting"}
        className="interactive-focus mt-10 w-full rounded-lg bg-ink px-6 py-3 font-medium text-canvas transition-opacity duration-200 hover:opacity-85 disabled:cursor-not-allowed disabled:bg-muted disabled:text-canvas disabled:opacity-100"
      >
        {status.kind === "submitting" ? "Submitting…" : "Submit for review"}
      </button>

      {status.kind === "error" && (
        <p className="mt-4 rounded-md border border-deep-coral/30 bg-coral/10 px-4 py-3 text-sm text-deep-coral">
          {status.message}
        </p>
      )}
    </form>
  );
}

function FormSection({
  eyebrow,
  first = false,
  children,
}: {
  eyebrow?: string;
  first?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className={first ? "" : "mt-10"}>
      {!first && <div className="hairline mb-6" />}
      {eyebrow && (
        <p className="mb-4 text-[13px] text-muted">{eyebrow}</p>
      )}
      <div className="space-y-6">{children}</div>
    </section>
  );
}

function FlyerPlaceholder({
  isOpen,
  onToggle,
}: {
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={isOpen}
      aria-controls="image-url-field"
      className="interactive-focus group mx-auto flex aspect-[4/5] w-full max-w-sm flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-ink/20 bg-canvas px-6 text-center transition-colors duration-200 hover:border-ink/40"
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="h-8 w-8 text-muted transition-colors duration-200 group-hover:text-ink/70"
      >
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M3 16l5-5 4 4 3-3 6 6" />
        <circle cx="8.5" cy="8.5" r="1.5" />
      </svg>
      <span className="font-display text-base text-ink">Add a flyer</span>
      <span className="text-sm text-muted">
        {isOpen ? "Hide URL field" : "or paste a URL"}
      </span>
    </button>
  );
}

function Field({
  label,
  name,
  type = "text",
  required = false,
  maxLength,
  placeholder,
  error,
}: {
  label: string;
  name: string;
  type?: string;
  required?: boolean;
  maxLength?: number;
  placeholder?: string;
  error?: string;
}) {
  const hintId = `${name}-hint`;
  const errorId = `${name}-error`;
  const describedBy = [required ? hintId : null, error ? errorId : null]
    .filter(Boolean)
    .join(" ");
  const baseClass =
    "interactive-focus mt-1 w-full rounded-md border border-ink/15 bg-canvas px-3 py-2 text-ink placeholder:text-muted focus:border-ink";
  const inputClass = error
    ? `${baseClass} border-deep-coral focus:border-deep-coral`
    : baseClass;

  return (
    <label className="block">
      <span className="flex items-center justify-between gap-3 text-sm font-medium text-ink/80">
        <span>{label}</span>
        {required && (
          <span id={hintId} className="text-xs font-normal text-muted">
            Required
          </span>
        )}
      </span>
      {type === "textarea" ? (
        <textarea
          name={name}
          required={required}
          maxLength={maxLength}
          placeholder={placeholder}
          rows={3}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy || undefined}
          className={inputClass}
        />
      ) : (
        <input
          name={name}
          type={type}
          required={required}
          maxLength={maxLength}
          placeholder={placeholder}
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

function SelectField({
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

function Checkbox({
  label,
  name,
  defaultChecked = false,
}: {
  label: string;
  name: string;
  defaultChecked?: boolean;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-ink/80">
      <input
        type="checkbox"
        name={name}
        defaultChecked={defaultChecked}
        className="interactive-focus h-4 w-4 rounded border-ink/15 text-ink"
      />
      {label}
    </label>
  );
}
