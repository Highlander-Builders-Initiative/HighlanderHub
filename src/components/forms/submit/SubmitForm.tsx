"use client";

import {
  useEffect,
  useRef,
  useState,
  type FocusEvent,
  type FormEvent,
} from "react";
import { track } from "@/lib/analytics";
import { validateEventTimes } from "@/lib/event-validation";
import { computeSubmitEndsAtLocal, type EndChoice } from "@/lib/submit-datetime";
import { supabase } from "@/lib/supabase";
import { SUBMIT_EVENT_CATEGORIES } from "@/types/event";
import { Checkbox, Field, FormSection, SelectField } from "./fields";
import { FlyerUpload } from "./FlyerUpload";
import { EndTimePicker } from "./EndTimePicker";
import { StartTimePicker } from "./StartTimePicker";
import {
  buildSubmissionRow,
  validateSubmissionFields,
  type FieldErrors,
} from "./submit-validation";
import { useFlyerUpload } from "./use-flyer-upload";

type Status =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "success" }
  | { kind: "error"; message: string };

export default function SubmitForm() {
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [isImageUrlOpen, setIsImageUrlOpen] = useState(false);
  const [isRsvpRequired, setIsRsvpRequired] = useState(false);
  const [startDate, setStartDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endChoice, setEndChoice] = useState<EndChoice>("1h");
  const [endCustomTime, setEndCustomTime] = useState("");
  const startedRef = useRef(false);
  const blurredRef = useRef(false);
  const { status: uploadStatus, uploadFlyer, clearUpload } = useFlyerUpload();

  const startsAtLocal =
    startDate && startTime ? `${startDate}T${startTime}` : "";
  const endsAtLocal = computeSubmitEndsAtLocal(
    startsAtLocal,
    endChoice,
    endCustomTime
  );

  useEffect(() => {
    track("submit_page_view", {});
  }, []);

  function onFirstInteract() {
    if (startedRef.current) return;
    startedRef.current = true;
    track("submission_start", {});
  }

  function onFirstBlur(e: FocusEvent<HTMLFormElement>) {
    if (blurredRef.current) return;
    const target = e.target;
    const name =
      target instanceof HTMLElement && "name" in target
        ? String(target.name)
        : "";
    if (!name) return;
    blurredRef.current = true;
    track("submission_first_blur", { field: name });
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const form = new FormData(e.currentTarget);
    const timeValidation = validateEventTimes(
      form.get("starts_at"),
      form.get("ends_at")
    );
    const nextFieldErrors = {
      ...validateSubmissionFields(form),
    };

    if (
      timeValidation.error &&
      timeValidation.field &&
      !nextFieldErrors[timeValidation.field]
    ) {
      nextFieldErrors[timeValidation.field] = timeValidation.error;
    }

    if (Object.keys(nextFieldErrors).length > 0) {
      if (nextFieldErrors.image_url) setIsImageUrlOpen(true);
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

    const row = buildSubmissionRow(
      form,
      timeValidation.startsAt,
      timeValidation.endsAt,
      uploadStatus.kind === "uploaded" ? uploadStatus.url : null
    );

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
          onClear={clearUpload}
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
        <SelectField
          label="Category"
          name="category"
          options={SUBMIT_EVENT_CATEGORIES}
        />
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
