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
import { SegmentedTimeInput } from "./SegmentedTimeInput";

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

      <div className="mt-4">
        <span className="block text-sm font-medium text-ink/80">Time</span>
        <SegmentedTimeInput
          value={timeValue}
          onChange={onChangeTime}
          onInteract={onInteract}
          error={Boolean(error)}
          ariaLabel="Start time"
        />
      </div>

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
