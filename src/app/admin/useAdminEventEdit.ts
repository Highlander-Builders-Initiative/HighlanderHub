"use client";

import { useReducer, useCallback, useMemo } from "react";
import { formatPacificDateTimeInput } from "@/lib/dates";
import { validateEventTimes } from "@/lib/events/validation";
import { coerceEventCategory } from "@/types/event";
import type { AdminEventRow, AdminEventUpdatePayload } from "./types";

type EditFormState = {
  title: string;
  description: string;
  startsAt: string;
  endsAt: string;
  location: string;
  host: string;
  hostHandle: string;
  category: string;
  contentKind: string;
  imageUrl: string;
  rsvpUrl: string;
  hasFreeFood: boolean;
  rsvpRequired: boolean;
};

type EditFormAction = {
  type: "patch";
  field: keyof EditFormState;
  value: string | boolean;
};

function formFromEvent(event: AdminEventRow): EditFormState {
  return {
    title: event.title,
    description: event.description || "",
    startsAt: formatPacificDateTimeInput(event.starts_at),
    endsAt: formatPacificDateTimeInput(event.ends_at ?? null),
    location: event.location,
    host: event.host,
    hostHandle: event.host_handle || "",
    // A row still carrying a retired category edits as uncategorized.
    category: coerceEventCategory(event.category),
    contentKind: event.content_kind,
    imageUrl: event.image_url || "",
    rsvpUrl: event.rsvp_url || "",
    hasFreeFood: event.has_free_food,
    rsvpRequired: event.rsvp_required,
  };
}

function formReducer(state: EditFormState, action: EditFormAction): EditFormState {
  return { ...state, [action.field]: action.value };
}

export type AdminEventUpdateBuildResult =
  | { ok: true; payload: AdminEventUpdatePayload }
  | { ok: false; error: string };

export function buildAdminEventUpdatePayload(
  form: EditFormState
): AdminEventUpdateBuildResult {
  const timeValidation = validateEventTimes(form.startsAt, form.endsAt);
  if (timeValidation.error || !timeValidation.startsAt) {
    return { ok: false, error: timeValidation.error ?? "Start time is invalid." };
  }

  return {
    ok: true,
    payload: {
      title: form.title,
      description: form.description,
      starts_at: timeValidation.startsAt,
      ends_at: timeValidation.endsAt,
      location: form.location,
      host: form.host,
      host_handle: form.hostHandle || null,
      category: form.category as AdminEventUpdatePayload["category"],
      content_kind: form.contentKind as AdminEventUpdatePayload["content_kind"],
      image_url: form.imageUrl || null,
      rsvp_url: form.rsvpUrl || null,
      has_free_food: form.hasFreeFood,
      rsvp_required: form.rsvpRequired,
    },
  };
}

/** Form state for one event; remount (key by id) to edit another. */
export function useAdminEventEdit(event: AdminEventRow) {
  const [form, dispatch] = useReducer(formReducer, event, formFromEvent);
  const saved = useMemo(() => formFromEvent(event), [event]);
  const isDirty = (Object.keys(saved) as (keyof EditFormState)[]).some(
    (field) => form[field] !== saved[field]
  );

  const setField = useCallback(
    <K extends keyof EditFormState>(field: K, value: EditFormState[K]) => {
      dispatch({ type: "patch", field, value });
    },
    []
  );

  const buildUpdatePayload = useCallback(
    (): AdminEventUpdateBuildResult => buildAdminEventUpdatePayload(form),
    [form]
  );

  return {
    form,
    isDirty,
    setField,
    buildUpdatePayload,
  };
}

export type AdminEventEditForm = ReturnType<typeof useAdminEventEdit>["form"];
export type SetAdminEventEditField = ReturnType<typeof useAdminEventEdit>["setField"];
