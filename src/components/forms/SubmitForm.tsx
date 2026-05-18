"use client";

import { useEffect, useState, useRef } from "react";
import { supabase } from "@/lib/supabase";
import { track } from "@/lib/analytics";
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
  | "location"
  | "host"
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

function validateRequiredFields(form: FormData): FieldErrors {
  return REQUIRED_FIELDS.reduce<FieldErrors>((errors, field) => {
    if (!String(form.get(field) ?? "").trim()) {
      errors[field] = "This field is required.";
    }
    return errors;
  }, {});
}

export default function SubmitForm() {
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const startedRef = useRef(false);

  useEffect(() => {
    track("submit_page_view", {});
  }, []);

  function onFirstInteract() {
    if (startedRef.current) return;
    startedRef.current = true;
    track("submission_start", {});
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const form = new FormData(e.currentTarget);
    const nextFieldErrors = validateRequiredFields(form);

    if (Object.keys(nextFieldErrors).length > 0) {
      setFieldErrors(nextFieldErrors);
      setStatus({ kind: "idle" });
      return;
    }

    setFieldErrors({});
    setStatus({ kind: "submitting" });

    const tagsRaw = (form.get("tags") as string) || "";

    const row = {
      title: form.get("title") as string,
      description: (form.get("description") as string) || "",
      starts_at: new Date(form.get("starts_at") as string).toISOString(),
      ends_at: form.get("ends_at")
        ? new Date(form.get("ends_at") as string).toISOString()
        : null,
      location: form.get("location") as string,
      host: form.get("host") as string,
      category: form.get("category") as EventCategory,
      tags: tagsRaw
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      source_url: (form.get("source_url") as string) || null,
      image_url: (form.get("image_url") as string) || null,
      is_free: form.get("is_free") === "on",
      rsvp_required: form.get("rsvp_required") === "on",
      rsvp_url: (form.get("rsvp_url") as string) || null,
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
      <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-6">
        <h2 className="font-serif text-2xl">Got it.</h2>
        <p className="mt-2 text-stone-700">
          Your event is queued for review. You&apos;ll see it on the bulletin
          once it&apos;s approved — usually within a day.
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      onFocusCapture={onFirstInteract}
      onChange={onFirstInteract}
      className="space-y-6"
    >
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
        placeholder="A sentence or two — what's happening, who's it for?"
      />

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <Field
          label="Starts"
          name="starts_at"
          type="datetime-local"
          required
          error={fieldErrors.starts_at}
        />
        <Field label="Ends (optional)" name="ends_at" type="datetime-local" />
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

      <SelectField label="Category" name="category" options={CATEGORIES} />

      <Field
        label="Tags (comma-separated)"
        name="tags"
        placeholder="cs, networking, free pizza"
      />

      <Field
        label="Event page or flyer URL (optional)"
        name="source_url"
        type="url"
      />
      <Field
        label="Image URL (optional)"
        name="image_url"
        type="url"
        placeholder="https://..."
      />

      <div className="flex gap-6">
        <Checkbox label="Free to attend" name="is_free" defaultChecked />
        <Checkbox label="RSVP required" name="rsvp_required" />
      </div>
      <Field
        label="RSVP / ticket URL (if required)"
        name="rsvp_url"
        type="url"
      />

      <hr className="border-stone-300" />

      <h2 className="font-serif text-xl">Your info</h2>
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

      <button
        type="submit"
        disabled={status.kind === "submitting"}
        className="interactive-focus w-full rounded-lg bg-stone-950 px-6 py-3 font-medium text-white transition-colors hover:bg-stone-800 disabled:cursor-not-allowed disabled:bg-stone-500 disabled:text-white disabled:opacity-100"
      >
        {status.kind === "submitting" ? "Submitting…" : "Submit for review"}
      </button>

      {status.kind === "error" && (
        <p className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
          {status.message}
        </p>
      )}
    </form>
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
    "interactive-focus mt-1 w-full rounded-md border border-stone-400 bg-stone-50 px-3 py-2 text-stone-950 placeholder:text-stone-600 focus:border-stone-950";
  const inputClass = error
    ? `${baseClass} border-red-700 focus:border-red-800`
    : baseClass;

  return (
    <label className="block">
      <span className="flex items-center justify-between gap-3 text-sm font-medium text-stone-700">
        <span>{label}</span>
        {required && (
          <span id={hintId} className="text-xs font-normal text-stone-500">
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
        <p id={errorId} className="mt-1 text-sm text-red-700">
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
      <span className="text-sm font-medium text-stone-700">{label}</span>
      <select
        name={name}
        defaultValue="club"
        className="interactive-focus mt-1 w-full rounded-md border border-stone-400 bg-stone-50 px-3 py-2 text-stone-950 focus:border-stone-950"
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
    <label className="flex items-center gap-2 text-sm text-stone-700">
      <input
        type="checkbox"
        name={name}
        defaultChecked={defaultChecked}
        className="interactive-focus h-4 w-4 rounded border-stone-400 text-stone-950"
      />
      {label}
    </label>
  );
}
