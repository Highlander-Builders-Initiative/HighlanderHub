"use client";

import { useState } from "react";
import {
  formatSubmitChipDate,
  formatSubmitPreviewDateTime,
  submitTodayDateInput,
  submitTomorrowDateInput,
  submitUpcomingFridayDateInput,
} from "@/lib/submit-datetime";
import { Chip } from "./fields";

export function StartTimePicker({
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
  const today = submitTodayDateInput();
  const tomorrow = submitTomorrowDateInput();
  const friday = submitUpcomingFridayDateInput();

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
          {`Fri ${formatSubmitChipDate(friday)}`}
        </Chip>
        <Chip
          active={isCustom || isPickOpen}
          onClick={() => {
            onInteract();
            setIsPickOpen((v) => !v);
          }}
        >
          {isCustom ? formatSubmitChipDate(dateValue) : "Pick a date"}
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
            {formatSubmitPreviewDateTime(previewLocal)}
          </span>
        </p>
      )}
      {error && <p className="mt-2 text-sm text-deep-coral">{error}</p>}
    </div>
  );
}
