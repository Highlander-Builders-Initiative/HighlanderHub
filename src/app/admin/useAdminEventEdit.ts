"use client";

import { useReducer, useCallback, useEffect } from "react";
import { formatPacificDateTimeInput } from "@/lib/dates";
import { validateEventTimes } from "@/lib/events/validation";
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
  isFree: boolean;
  hasFreeFood: boolean;
  rsvpRequired: boolean;
};

type EditFormAction =
  | { type: "load"; event: AdminEventRow }
  | { type: "patch"; field: keyof EditFormState; value: string | boolean };

const initialFormState: EditFormState = {
  title: "",
  description: "",
  startsAt: "",
  endsAt: "",
  location: "",
  host: "",
  hostHandle: "",
  category: "",
  contentKind: "student_event",
  imageUrl: "",
  rsvpUrl: "",
  isFree: true,
  hasFreeFood: false,
  rsvpRequired: false,
};

function formReducer(state: EditFormState, action: EditFormAction): EditFormState {
  if (action.type === "load") {
    const event = action.event;
    return {
      title: event.title,
      description: event.description || "",
      startsAt: formatPacificDateTimeInput(event.starts_at),
      endsAt: formatPacificDateTimeInput(event.ends_at ?? null),
      location: event.location,
      host: event.host,
      hostHandle: event.host_handle || "",
      category: event.category,
      contentKind: event.content_kind,
      imageUrl: event.image_url || "",
      rsvpUrl: event.rsvp_url || "",
      isFree: event.is_free,
      hasFreeFood: event.has_free_food,
      rsvpRequired: event.rsvp_required,
    };
  }
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
      is_free: form.isFree,
      has_free_food: form.hasFreeFood,
      rsvp_required: form.rsvpRequired,
    },
  };
}

export function useAdminEventEdit(event: AdminEventRow | null) {
  const [form, dispatch] = useReducer(formReducer, initialFormState);

  useEffect(() => {
    if (event) dispatch({ type: "load", event });
  }, [event]);

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
    setField,
    buildUpdatePayload,
  };
}

export type AdminEventEditForm = ReturnType<typeof useAdminEventEdit>["form"];
export type SetAdminEventEditField = ReturnType<typeof useAdminEventEdit>["setField"];
