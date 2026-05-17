"use client";

import { useState, useRef } from "react";
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

export default function SubmitForm() {
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const startedRef = useRef(false);

  function onFirstInteract() {
    if (startedRef.current) return;
    startedRef.current = true;
    track("submission_start", {});
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus({ kind: "submitting" });

    const form = new FormData(e.currentTarget);
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
      <Field label="Event title" name="title" required maxLength={200} />
      <Field
        label="Description"
        name="description"
        type="textarea"
        placeholder="A sentence or two — what's happening, who's it for?"
      />

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <Field label="Starts" name="starts_at" type="datetime-local" required />
        <Field label="Ends (optional)" name="ends_at" type="datetime-local" />
      </div>

      <Field
        label="Location"
        name="location"
        required
        placeholder="HUB 302, or 'Bell Tower lawn'"
      />
      <Field
        label="Host / organization"
        name="host"
        required
        placeholder="ACM at UCR"
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
      <Field label="Your name" name="submitter_name" required />
      <Field
        label="Your email"
        name="submitter_email"
        type="email"
        required
      />
      <Field
        label="Org affiliation (optional)"
        name="submitter_org"
        placeholder="ACM at UCR"
      />

      <button
        type="submit"
        disabled={status.kind === "submitting"}
        className="w-full rounded-lg bg-stone-900 px-6 py-3 font-medium text-stone-50 hover:bg-stone-800 disabled:opacity-50"
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
}: {
  label: string;
  name: string;
  type?: string;
  required?: boolean;
  maxLength?: number;
  placeholder?: string;
}) {
  const baseClass =
    "mt-1 w-full rounded-md border border-stone-300 bg-stone-50 px-3 py-2 text-stone-900 placeholder:text-stone-400 focus:border-stone-900 focus:outline-none";
  return (
    <label className="block">
      <span className="text-sm font-medium text-stone-700">
        {label}
        {required && <span className="text-red-600"> *</span>}
      </span>
      {type === "textarea" ? (
        <textarea
          name={name}
          required={required}
          maxLength={maxLength}
          placeholder={placeholder}
          rows={3}
          className={baseClass}
        />
      ) : (
        <input
          name={name}
          type={type}
          required={required}
          maxLength={maxLength}
          placeholder={placeholder}
          className={baseClass}
        />
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
        className="mt-1 w-full rounded-md border border-stone-300 bg-stone-50 px-3 py-2 text-stone-900 focus:border-stone-900 focus:outline-none"
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
        className="h-4 w-4 rounded border-stone-300"
      />
      {label}
    </label>
  );
}
