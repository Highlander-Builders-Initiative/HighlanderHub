"use client";

import { useReducer, useCallback, useEffect } from "react";
import type { AdminEventRow, AdminEventUpdatePayload } from "./types";

export function formatISOToLocal(isoStr: string | null): string {
  if (!isoStr) return "";
  try {
    const date = new Date(isoStr);
    const tzOffset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - tzOffset).toISOString().slice(0, 16);
  } catch {
    return "";
  }
}

export function formatLocalToISO(localStr: string): string {
  if (!localStr) return "";
  return new Date(localStr).toISOString();
}

type EditFormState = {
  title: string;
  description: string;
  startsAt: string;
  endsAt: string;
  location: string;
  host: string;
  hostHandle: string;
  category: string;
  imageUrl: string;
  rsvpUrl: string;
  isFree: boolean;
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
  imageUrl: "",
  rsvpUrl: "",
  isFree: true,
  rsvpRequired: false,
};

function formReducer(state: EditFormState, action: EditFormAction): EditFormState {
  if (action.type === "load") {
    const event = action.event;
    return {
      title: event.title,
      description: event.description || "",
      startsAt: formatISOToLocal(event.starts_at),
      endsAt: formatISOToLocal(event.ends_at ?? null),
      location: event.location,
      host: event.host,
      hostHandle: event.host_handle || "",
      category: event.category,
      imageUrl: event.image_url || "",
      rsvpUrl: event.rsvp_url || "",
      isFree: event.is_free,
      rsvpRequired: event.rsvp_required,
    };
  }
  return { ...state, [action.field]: action.value };
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

  const buildUpdatePayload = useCallback((): AdminEventUpdatePayload => {
    return {
      title: form.title,
      description: form.description,
      starts_at: formatLocalToISO(form.startsAt),
      ends_at: form.endsAt ? formatLocalToISO(form.endsAt) : null,
      location: form.location,
      host: form.host,
      host_handle: form.hostHandle || null,
      category: form.category as AdminEventUpdatePayload["category"],
      image_url: form.imageUrl || null,
      rsvp_url: form.rsvpUrl || null,
      is_free: form.isFree,
      rsvp_required: form.rsvpRequired,
    };
  }, [form]);

  return {
    form,
    setField,
    buildUpdatePayload,
  };
}

export type AdminEventEditForm = ReturnType<typeof useAdminEventEdit>["form"];
export type SetAdminEventEditField = ReturnType<typeof useAdminEventEdit>["setField"];
