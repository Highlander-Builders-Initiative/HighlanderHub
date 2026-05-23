"use client";

import {
  computeSubmitEndsAtLocal,
  formatSubmitPreviewTime,
  type EndChoice,
} from "@/lib/submit-datetime";
import { Chip } from "./fields";

export function EndTimePicker({
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
  const previewLocal = computeSubmitEndsAtLocal(
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
          Until <span className="font-mono">{formatSubmitPreviewTime(previewLocal)}</span>
        </p>
      )}
      {error && <p className="mt-2 text-sm text-deep-coral">{error}</p>}
    </div>
  );
}
