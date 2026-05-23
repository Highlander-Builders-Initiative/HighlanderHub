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

type UploadStatus =
  | { kind: "idle" }
  | { kind: "uploading" }
  | { kind: "uploaded"; url: string }
  | { kind: "error"; message: string };

const FLYER_BUCKET = "submission-flyers";
const FLYER_MAX_BYTES = 5 * 1024 * 1024;
const FLYER_MIME_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const FLYER_EXT_BY_TYPE: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
};

type EndChoice = "30m" | "1h" | "1h30" | "custom" | "none";

const END_CHOICE_MINUTES: Record<Exclude<EndChoice, "custom" | "none">, number> = {
  "30m": 30,
  "1h": 60,
  "1h30": 90,
};

function padTwo(n: number): string {
  return String(n).padStart(2, "0");
}

function toDateInput(d: Date): string {
  return `${d.getFullYear()}-${padTwo(d.getMonth() + 1)}-${padTwo(d.getDate())}`;
}

function toTimeInput(d: Date): string {
  return `${padTwo(d.getHours())}:${padTwo(d.getMinutes())}`;
}

function toLocalDateTime(d: Date): string {
  return `${toDateInput(d)}T${toTimeInput(d)}`;
}

function addMinutesLocal(local: string, minutes: number): string {
  const d = new Date(local);
  if (!Number.isFinite(d.getTime())) return "";
  d.setMinutes(d.getMinutes() + minutes);
  return toLocalDateTime(d);
}

function todayDateInput(): string {
  return toDateInput(new Date());
}

function tomorrowDateInput(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return toDateInput(d);
}

function upcomingFridayDateInput(): string {
  const now = new Date();
  const day = now.getDay();
  let delta = (5 - day + 7) % 7;
  if (delta <= 1) delta += 7;
  const d = new Date(now);
  d.setDate(now.getDate() + delta);
  return toDateInput(d);
}

function formatChipDate(input: string): string {
  if (!input) return "";
  const d = new Date(`${input}T00:00`);
  if (!Number.isFinite(d.getTime())) return "";
  const month = d.toLocaleDateString(undefined, { month: "short" });
  return `${month} ${d.getDate()}`;
}

function formatPreviewDateTime(local: string): string {
  if (!local) return "";
  const d = new Date(local);
  if (!Number.isFinite(d.getTime())) return "";
  const weekday = d.toLocaleDateString(undefined, { weekday: "short" });
  const month = d.toLocaleDateString(undefined, { month: "short" });
  const time = d.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
  return `${weekday}, ${month} ${d.getDate()} · ${time}`;
}

function formatPreviewTime(local: string): string {
  if (!local) return "";
  const d = new Date(local);
  if (!Number.isFinite(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

function computeEndsAtLocal(
  startsAtLocal: string,
  choice: EndChoice,
  customTime: string
): string {
  if (!startsAtLocal) return "";
  if (choice === "none") return "";
  if (choice === "custom") {
    if (!customTime) return "";
    const datePart = startsAtLocal.slice(0, 10);
    return `${datePart}T${customTime}`;
  }
  return addMinutesLocal(startsAtLocal, END_CHOICE_MINUTES[choice]);
}

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
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>({ kind: "idle" });
  const [isRsvpRequired, setIsRsvpRequired] = useState(false);
  const [startDate, setStartDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endChoice, setEndChoice] = useState<EndChoice>("1h");
  const [endCustomTime, setEndCustomTime] = useState("");
  const startedRef = useRef(false);
  const blurredRef = useRef(false);

  const startsAtLocal =
    startDate && startTime ? `${startDate}T${startTime}` : "";
  const endsAtLocal = computeEndsAtLocal(
    startsAtLocal,
    endChoice,
    endCustomTime
  );

  useEffect(() => {
    track("submit_page_view", {});
  }, []);

  useEffect(() => {
    if (fieldErrors.image_url) setIsImageUrlOpen(true);
  }, [fieldErrors.image_url]);

  useEffect(() => {
    if (fieldErrors.rsvp_url) setIsRsvpRequired(true);
  }, [fieldErrors.rsvp_url]);

  function onFirstInteract() {
    if (startedRef.current) return;
    startedRef.current = true;
    track("submission_start", {});
  }

  function onFirstBlur(e: React.FocusEvent<HTMLFormElement>) {
    if (blurredRef.current) return;
    const target = e.target as unknown as { name?: string };
    const name = target?.name;
    if (!name) return;
    blurredRef.current = true;
    track("submission_first_blur", { field: name });
  }

  async function uploadFlyer(file: File) {
    if (!FLYER_MIME_TYPES.has(file.type)) {
      setUploadStatus({
        kind: "error",
        message: "Use a JPG, PNG, or WebP image.",
      });
      return;
    }
    if (file.size > FLYER_MAX_BYTES) {
      setUploadStatus({
        kind: "error",
        message: "Image must be 5 MB or smaller.",
      });
      return;
    }

    setUploadStatus({ kind: "uploading" });

    const ext = FLYER_EXT_BY_TYPE[file.type] ?? "jpg";
    const path = `${crypto.randomUUID()}.${ext}`;

    const { data, error } = await supabase.storage
      .from(FLYER_BUCKET)
      .upload(path, file, {
        contentType: file.type,
        upsert: false,
      });

    if (error || !data) {
      track("flyer_upload_error", { message: error?.message ?? "unknown" });
      setUploadStatus({
        kind: "error",
        message: "Couldn’t upload. Try again, or paste a URL below.",
      });
      return;
    }

    const { data: publicData } = supabase.storage
      .from(FLYER_BUCKET)
      .getPublicUrl(data.path);

    track("flyer_uploaded", { size: file.size, type: file.type });
    setUploadStatus({ kind: "uploaded", url: publicData.publicUrl });
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
    const uploadedImageUrl =
      uploadStatus.kind === "uploaded" ? uploadStatus.url : null;
    const imageUrl =
      uploadedImageUrl ?? normalizeHttpUrl(form.get("image_url"));
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
      setStatus({
        kind: "error",
        message:
          "Something went wrong saving this. Try again, or message us on Instagram if it keeps failing.",
      });
      return;
    }
    track("submission_complete", {});
    setStatus({ kind: "success" });
  }

  if (status.kind === "success") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="rounded-lg border border-deep-leaf/30 bg-leaf/10 p-6"
      >
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
      onBlurCapture={onFirstBlur}
    >
      <FormSection first>
        <FlyerUpload
          status={uploadStatus}
          isUrlOpen={isImageUrlOpen}
          onFile={uploadFlyer}
          onClear={() => setUploadStatus({ kind: "idle" })}
          onToggleUrl={() => setIsImageUrlOpen((v) => !v)}
        />
        <div
          id="image-url-field"
          className={
            uploadStatus.kind !== "uploaded" && isImageUrlOpen
              ? "mt-4"
              : "hidden"
          }
        >
          <Field
            label="Flyer URL"
            name="image_url"
            type="url"
            optional
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
          showCounter
          error={fieldErrors.title}
        />
        <Field
          label="Description"
          name="description"
          type="textarea"
          optional
          rows={4}
          autoGrow
          placeholder="A sentence or two: what's happening, who's it for?"
        />
        <SelectField label="Category" name="category" options={CATEGORIES} />
        <Field
          label="Tags"
          name="tags"
          optional
          placeholder="cs, networking, free pizza"
        />
      </FormSection>

      <FormSection eyebrow="when and where">
        <StartTimePicker
          dateValue={startDate}
          timeValue={startTime}
          onChangeDate={setStartDate}
          onChangeTime={setStartTime}
          onInteract={onFirstInteract}
          error={fieldErrors.starts_at}
        />
        <EndTimePicker
          startsAtLocal={startsAtLocal}
          endChoice={endChoice}
          endCustomTime={endCustomTime}
          onChangeChoice={setEndChoice}
          onChangeCustomTime={setEndCustomTime}
          onInteract={onFirstInteract}
          error={fieldErrors.ends_at}
        />
        <input type="hidden" name="starts_at" value={startsAtLocal} />
        <input type="hidden" name="ends_at" value={endsAtLocal} />
        <Field
          label="Location"
          name="location"
          required
          placeholder="HUB 302, or 'Bell Tower lawn'"
          error={fieldErrors.location}
        />
        <Field
          label="Hosted by"
          name="host"
          required
          placeholder="ACM at UCR"
          error={fieldErrors.host}
        />
      </FormSection>

      <FormSection eyebrow="links and tickets">
        <Field
          label="Event page"
          name="source_url"
          type="url"
          optional
          placeholder="https://..."
          error={fieldErrors.source_url}
        />
        <div className="flex gap-6">
          <Checkbox label="Free to attend" name="is_free" defaultChecked />
          <Checkbox
            label="RSVP required"
            name="rsvp_required"
            onChange={setIsRsvpRequired}
          />
        </div>
        {isRsvpRequired && (
          <div className="animate-field-reveal">
            <Field
              label="Ticket link"
              name="rsvp_url"
              type="url"
              required
              placeholder="https://..."
              error={fieldErrors.rsvp_url}
            />
          </div>
        )}
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
          label="Org affiliation"
          name="submitter_org"
          optional
          placeholder="ACM at UCR"
        />
      </FormSection>

      <button
        type="submit"
        disabled={status.kind === "submitting"}
        className="interactive-focus mt-10 w-full rounded-lg bg-ink px-6 py-3 font-medium text-canvas transition-opacity duration-200 hover:opacity-85 disabled:cursor-not-allowed disabled:bg-muted disabled:text-canvas disabled:opacity-100 sm:w-auto sm:min-w-[220px]"
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

function FlyerUpload({
  status,
  isUrlOpen,
  onFile,
  onClear,
  onToggleUrl,
}: {
  status: UploadStatus;
  isUrlOpen: boolean;
  onFile: (file: File) => void;
  onClear: () => void;
  onToggleUrl: () => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  function pick() {
    fileInputRef.current?.click();
  }

  return (
    <div className="mx-auto w-full max-w-[200px]">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          e.target.value = "";
        }}
        className="sr-only"
        aria-hidden="true"
        tabIndex={-1}
      />

      {status.kind === "uploaded" ? (
        <FlyerUploadedTile url={status.url} onReplace={pick} onClear={onClear} />
      ) : (
        <button
          type="button"
          onClick={status.kind === "uploading" ? undefined : pick}
          disabled={status.kind === "uploading"}
          className="interactive-focus group flex aspect-[4/5] w-full flex-col items-center justify-center gap-1.5 rounded-xl border border-dashed border-ink/20 bg-canvas px-4 text-center transition-colors duration-200 hover:border-ink/40 disabled:cursor-progress disabled:opacity-70"
        >
          {status.kind === "uploading" ? (
            <>
              <FlyerSpinner />
              <span className="font-display text-sm text-ink">Uploading…</span>
            </>
          ) : (
            <>
              <FlyerIcon />
              <span className="font-display text-sm text-ink">Add a flyer</span>
              <span className="text-xs text-muted">JPG, PNG, or WebP</span>
            </>
          )}
        </button>
      )}

      {status.kind === "error" && (
        <p className="mt-2 text-center text-xs text-deep-coral">
          {status.message}
        </p>
      )}

      {status.kind !== "uploaded" && (
        <button
          type="button"
          onClick={onToggleUrl}
          aria-expanded={isUrlOpen}
          aria-controls="image-url-field"
          className="interactive-focus mt-3 block w-full text-center text-xs text-muted underline-offset-2 transition-colors duration-200 hover:text-ink/70 hover:underline"
        >
          {isUrlOpen ? "Hide URL field" : "or paste a URL"}
        </button>
      )}
    </div>
  );
}

function FlyerUploadedTile({
  url,
  onReplace,
  onClear,
}: {
  url: string;
  onReplace: () => void;
  onClear: () => void;
}) {
  return (
    <div className="space-y-2">
      <div className="relative aspect-[4/5] w-full overflow-hidden rounded-xl border border-ink/15 bg-surface">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={url}
          alt="Flyer preview"
          className="h-full w-full object-cover"
        />
      </div>
      <div className="flex items-center justify-center gap-3 text-xs">
        <button
          type="button"
          onClick={onReplace}
          className="interactive-focus text-muted underline-offset-2 transition-colors duration-200 hover:text-ink/70 hover:underline"
        >
          Replace
        </button>
        <span aria-hidden="true" className="text-ink/20">·</span>
        <button
          type="button"
          onClick={onClear}
          className="interactive-focus text-muted underline-offset-2 transition-colors duration-200 hover:text-deep-coral hover:underline"
        >
          Remove
        </button>
      </div>
    </div>
  );
}

function FlyerIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-6 w-6 text-muted transition-colors duration-200 group-hover:text-ink/70"
    >
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 16l5-5 4 4 3-3 6 6" />
      <circle cx="8.5" cy="8.5" r="1.5" />
    </svg>
  );
}

function FlyerSpinner() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      aria-hidden="true"
      className="h-6 w-6 animate-spin text-ink/70"
    >
      <path d="M21 12a9 9 0 1 1-9-9" />
    </svg>
  );
}

function Field({
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
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) {
    if (showCounter) setLength(e.target.value.length);
    if (autoGrow && textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }

  const counterAtRisk = maxLength != null && length >= Math.floor(maxLength * 0.8);

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

function Chip({
  active,
  disabled,
  onClick,
  children,
}: {
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
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

function StartTimePicker({
  dateValue,
  timeValue,
  onChangeDate,
  onChangeTime,
  onInteract,
  error,
}: {
  dateValue: string;
  timeValue: string;
  onChangeDate: (v: string) => void;
  onChangeTime: (v: string) => void;
  onInteract: () => void;
  error?: string;
}) {
  const [isPickOpen, setIsPickOpen] = useState(false);
  const today = todayDateInput();
  const tomorrow = tomorrowDateInput();
  const friday = upcomingFridayDateInput();

  function select(value: string) {
    onInteract();
    onChangeDate(value);
    setIsPickOpen(false);
  }

  const isCustom =
    dateValue !== "" &&
    dateValue !== today &&
    dateValue !== tomorrow &&
    dateValue !== friday;

  const previewLocal = dateValue && timeValue ? `${dateValue}T${timeValue}` : "";

  return (
    <div>
      <div className="mb-2">
        <span className="text-sm font-medium text-ink/80">Starts</span>
      </div>

      <div className="flex flex-wrap gap-2">
        <Chip active={dateValue === today} onClick={() => select(today)}>
          Today
        </Chip>
        <Chip active={dateValue === tomorrow} onClick={() => select(tomorrow)}>
          Tomorrow
        </Chip>
        <Chip active={dateValue === friday} onClick={() => select(friday)}>
          {`Fri ${formatChipDate(friday)}`}
        </Chip>
        <Chip
          active={isCustom || isPickOpen}
          onClick={() => {
            onInteract();
            setIsPickOpen((v) => !v);
          }}
        >
          {isCustom ? formatChipDate(dateValue) : "Pick a date"}
        </Chip>
      </div>

      {(isPickOpen || isCustom) && (
        <label className="mt-3 block animate-field-reveal">
          <span className="sr-only">Pick a date</span>
          <input
            type="date"
            value={dateValue}
            onChange={(e) => {
              onInteract();
              onChangeDate(e.target.value);
            }}
            className="interactive-focus w-full rounded-md border border-ink/15 bg-canvas px-3 py-2 text-ink focus:border-ink sm:w-auto"
          />
        </label>
      )}

      <label className="mt-4 block">
        <span className="text-sm font-medium text-ink/80">Time</span>
        <input
          type="time"
          value={timeValue}
          onChange={(e) => {
            onInteract();
            onChangeTime(e.target.value);
          }}
          className={`interactive-focus mt-1 block w-full rounded-md border bg-canvas px-3 py-2 text-ink focus:border-ink sm:w-auto ${
            error ? "border-deep-coral" : "border-ink/15"
          }`}
        />
      </label>

      {previewLocal && !error && (
        <p className="mt-3 text-xs text-muted">
          <span className="font-mono">
            {formatPreviewDateTime(previewLocal)}
          </span>
        </p>
      )}
      {error && <p className="mt-2 text-sm text-deep-coral">{error}</p>}
    </div>
  );
}

function EndTimePicker({
  startsAtLocal,
  endChoice,
  endCustomTime,
  onChangeChoice,
  onChangeCustomTime,
  onInteract,
  error,
}: {
  startsAtLocal: string;
  endChoice: EndChoice;
  endCustomTime: string;
  onChangeChoice: (c: EndChoice) => void;
  onChangeCustomTime: (v: string) => void;
  onInteract: () => void;
  error?: string;
}) {
  const disabled = !startsAtLocal;
  const previewLocal = computeEndsAtLocal(
    startsAtLocal,
    endChoice,
    endCustomTime
  );

  function pick(choice: EndChoice) {
    onInteract();
    onChangeChoice(choice);
  }

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium text-ink/80">Ends</span>
        <span className="text-xs font-normal text-muted">Optional</span>
      </div>

      <div className="flex flex-wrap gap-2">
        <Chip
          active={endChoice === "30m"}
          disabled={disabled}
          onClick={() => pick("30m")}
        >
          30 min
        </Chip>
        <Chip
          active={endChoice === "1h"}
          disabled={disabled}
          onClick={() => pick("1h")}
        >
          1 hr
        </Chip>
        <Chip
          active={endChoice === "1h30"}
          disabled={disabled}
          onClick={() => pick("1h30")}
        >
          1.5 hr
        </Chip>
        <Chip
          active={endChoice === "custom"}
          disabled={disabled}
          onClick={() => pick("custom")}
        >
          Custom
        </Chip>
        <Chip
          active={endChoice === "none"}
          disabled={disabled}
          onClick={() => pick("none")}
        >
          No end time
        </Chip>
      </div>

      {disabled && (
        <p className="mt-2 text-xs text-muted">Pick a start time first.</p>
      )}

      {!disabled && endChoice === "custom" && (
        <label className="mt-3 block animate-field-reveal">
          <span className="sr-only">Custom end time</span>
          <input
            type="time"
            value={endCustomTime}
            onChange={(e) => {
              onInteract();
              onChangeCustomTime(e.target.value);
            }}
            className={`interactive-focus block w-full rounded-md border bg-canvas px-3 py-2 text-ink focus:border-ink sm:w-auto ${
              error ? "border-deep-coral" : "border-ink/15"
            }`}
          />
        </label>
      )}

      {!disabled && previewLocal && !error && (
        <p className="mt-3 text-xs text-muted">
          Until <span className="font-mono">{formatPreviewTime(previewLocal)}</span>
        </p>
      )}
      {error && <p className="mt-2 text-sm text-deep-coral">{error}</p>}
    </div>
  );
}
