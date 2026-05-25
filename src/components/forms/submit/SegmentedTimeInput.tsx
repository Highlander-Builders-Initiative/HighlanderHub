"use client";

import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
} from "react";

type Period = "AM" | "PM";

function to24h(hours12: number, period: Period): number {
  if (period === "AM") return hours12 === 12 ? 0 : hours12;
  return hours12 === 12 ? 12 : hours12 + 12;
}

function from24h(value: string): {
  h: string;
  m: string;
  period: Period;
} {
  if (!value || !value.includes(":")) {
    return { h: "", m: "", period: "AM" };
  }
  const [hStr, mStr] = value.split(":");
  const h24 = parseInt(hStr, 10);
  const mm = parseInt(mStr, 10);
  if (Number.isNaN(h24) || Number.isNaN(mm)) {
    return { h: "", m: "", period: "AM" };
  }
  const period: Period = h24 >= 12 ? "PM" : "AM";
  let h12 = h24 % 12;
  if (h12 === 0) h12 = 12;
  return {
    h: String(h12).padStart(2, "0"),
    m: String(mm).padStart(2, "0"),
    period,
  };
}

function isComplete(h: string, m: string): boolean {
  if (h.length === 0 || m.length === 0) return false;
  const hi = parseInt(h, 10);
  const mi = parseInt(m, 10);
  return hi >= 1 && hi <= 12 && mi >= 0 && mi <= 59;
}

function commitValue(
  h: string,
  m: string,
  period: Period,
  onChange: (v: string) => void
) {
  if (!isComplete(h, m)) {
    onChange("");
    return;
  }
  const h24 = to24h(parseInt(h, 10), period);
  const mm = parseInt(m, 10);
  onChange(`${String(h24).padStart(2, "0")}:${String(mm).padStart(2, "0")}`);
}

export function SegmentedTimeInput({
  value,
  onChange,
  onInteract,
  error,
  ariaLabel = "Time",
}: {
  value: string;
  onChange: (v: string) => void;
  onInteract?: () => void;
  error?: boolean;
  ariaLabel?: string;
}) {
  const initial = from24h(value);
  const [h, setH] = useState(initial.h);
  const [m, setM] = useState(initial.m);
  const [period, setPeriod] = useState<Period>(initial.period);
  const hRef = useRef<HTMLInputElement>(null);
  const mRef = useRef<HTMLInputElement>(null);
  const pRef = useRef<HTMLButtonElement>(null);
  const hStateRef = useRef(initial.h);
  const mStateRef = useRef(initial.m);
  const periodStateRef = useRef<Period>(initial.period);
  const lastEmittedRef = useRef(value);

  function updateH(next: string) {
    hStateRef.current = next;
    setH(next);
  }
  function updateM(next: string) {
    mStateRef.current = next;
    setM(next);
  }
  function updatePeriod(next: Period) {
    periodStateRef.current = next;
    setPeriod(next);
  }

  useEffect(() => {
    if (value === lastEmittedRef.current) return;
    const next = from24h(value);
    updateH(next.h);
    updateM(next.m);
    updatePeriod(next.period);
    lastEmittedRef.current = value;
  }, [value]);

  function emit(nextH: string, nextM: string, nextPeriod: Period) {
    const previous = lastEmittedRef.current;
    if (!isComplete(nextH, nextM)) {
      if (previous !== "") {
        lastEmittedRef.current = "";
        onChange("");
      }
      return;
    }
    const h24 = to24h(parseInt(nextH, 10), nextPeriod);
    const next = `${String(h24).padStart(2, "0")}:${String(
      parseInt(nextM, 10)
    ).padStart(2, "0")}`;
    if (next === previous) return;
    lastEmittedRef.current = next;
    onChange(next);
  }

  function onHoursChange(e: ChangeEvent<HTMLInputElement>) {
    onInteract?.();
    const digits = e.target.value.replace(/\D/g, "").slice(0, 2);
    updateH(digits);

    if (digits.length === 2) {
      const n = parseInt(digits, 10);
      if (n >= 1 && n <= 12) {
        emit(digits, mStateRef.current, periodStateRef.current);
        mRef.current?.focus();
        mRef.current?.select();
        return;
      }
      // Invalid two-digit (00, 13-19, etc.) — keep focus and let user correct.
      emit("", mStateRef.current, periodStateRef.current);
      return;
    }

    if (digits.length === 1) {
      const n = parseInt(digits, 10);
      // Single digits 2-9 can't be followed by another digit (max is 12),
      // so auto-advance immediately. Pad the displayed value to two digits
      // since we're committing it as final.
      if (n >= 2 && n <= 9) {
        const padded = digits.padStart(2, "0");
        updateH(padded);
        emit(padded, mStateRef.current, periodStateRef.current);
        mRef.current?.focus();
        mRef.current?.select();
        return;
      }
    }

    emit(digits, mStateRef.current, periodStateRef.current);
  }

  function onMinutesChange(e: ChangeEvent<HTMLInputElement>) {
    onInteract?.();
    const digits = e.target.value.replace(/\D/g, "").slice(0, 2);
    updateM(digits);

    if (digits.length === 2) {
      const n = parseInt(digits, 10);
      if (n >= 0 && n <= 59) {
        emit(hStateRef.current, digits, periodStateRef.current);
        pRef.current?.focus();
        return;
      }
      emit(hStateRef.current, "", periodStateRef.current);
      return;
    }

    if (digits.length === 1) {
      const n = parseInt(digits, 10);
      // Single digits 6-9 can't be valid as a leading minute digit (max is 59),
      // so auto-advance immediately and pad the displayed value.
      if (n >= 6 && n <= 9) {
        const padded = digits.padStart(2, "0");
        updateM(padded);
        emit(hStateRef.current, padded, periodStateRef.current);
        pRef.current?.focus();
        return;
      }
    }

    emit(hStateRef.current, digits, periodStateRef.current);
  }

  function onHoursKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowRight") {
      const input = e.currentTarget;
      if (input.selectionStart === input.value.length) {
        e.preventDefault();
        mRef.current?.focus();
        mRef.current?.select();
      }
    } else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      const currentH = hStateRef.current;
      const current = parseInt(currentH || "0", 10) || (e.key === "ArrowUp" ? 0 : 13);
      let next = e.key === "ArrowUp" ? current + 1 : current - 1;
      if (next > 12) next = 1;
      if (next < 1) next = 12;
      const padded = String(next).padStart(2, "0");
      updateH(padded);
      emit(padded, mStateRef.current, periodStateRef.current);
      onInteract?.();
    }
  }

  function onMinutesKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowLeft") {
      const input = e.currentTarget;
      if (input.selectionStart === 0) {
        e.preventDefault();
        hRef.current?.focus();
        hRef.current?.select();
      }
    } else if (e.key === "ArrowRight") {
      const input = e.currentTarget;
      if (input.selectionStart === input.value.length) {
        e.preventDefault();
        pRef.current?.focus();
      }
    } else if (e.key === "Backspace" && mStateRef.current.length === 0) {
      e.preventDefault();
      hRef.current?.focus();
      hRef.current?.select();
    } else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      const current = parseInt(mStateRef.current || "0", 10);
      let next =
        e.key === "ArrowUp" ? (current + 1) % 60 : (current + 59) % 60;
      const padded = String(next).padStart(2, "0");
      updateM(padded);
      emit(hStateRef.current, padded, periodStateRef.current);
      onInteract?.();
    }
  }

  function onPeriodKeyDown(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key === "a" || e.key === "A") {
      e.preventDefault();
      updatePeriod("AM");
      emit(hStateRef.current, mStateRef.current, "AM");
      onInteract?.();
    } else if (e.key === "p" || e.key === "P") {
      e.preventDefault();
      updatePeriod("PM");
      emit(hStateRef.current, mStateRef.current, "PM");
      onInteract?.();
    } else if (
      e.key === "ArrowUp" ||
      e.key === "ArrowDown" ||
      e.key === " "
    ) {
      e.preventDefault();
      togglePeriod();
    } else if (e.key === "ArrowLeft" || e.key === "Backspace") {
      e.preventDefault();
      mRef.current?.focus();
      mRef.current?.select();
    }
  }

  function togglePeriod() {
    const next: Period = periodStateRef.current === "AM" ? "PM" : "AM";
    updatePeriod(next);
    emit(hStateRef.current, mStateRef.current, next);
    onInteract?.();
  }

  function onHoursBlur() {
    const currentH = hStateRef.current;
    if (currentH.length === 1) {
      const padded = currentH.padStart(2, "0");
      const n = parseInt(padded, 10);
      if (n >= 1 && n <= 12) {
        updateH(padded);
        emit(padded, mStateRef.current, periodStateRef.current);
      }
    }
  }

  function onMinutesBlur() {
    const currentM = mStateRef.current;
    if (currentM.length === 1) {
      const padded = currentM.padStart(2, "0");
      updateM(padded);
      emit(hStateRef.current, padded, periodStateRef.current);
    }
  }

  const borderClass = error
    ? "border-deep-coral"
    : "border-ink/15 focus-within:border-ink";

  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={`interactive-focus mt-1 inline-flex w-full items-center gap-0.5 rounded-md border bg-canvas px-3 py-2 text-ink tabular-nums sm:w-auto ${borderClass}`}
    >
      <input
        ref={hRef}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        aria-label="Hours"
        placeholder="HH"
        value={h}
        onChange={onHoursChange}
        onKeyDown={onHoursKeyDown}
        onBlur={onHoursBlur}
        onFocus={(e) => e.currentTarget.select()}
        className="w-7 bg-transparent text-center outline-none placeholder:text-muted/60"
      />
      <span aria-hidden="true" className="text-ink/60">
        :
      </span>
      <input
        ref={mRef}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        aria-label="Minutes"
        placeholder="MM"
        value={m}
        onChange={onMinutesChange}
        onKeyDown={onMinutesKeyDown}
        onBlur={onMinutesBlur}
        onFocus={(e) => e.currentTarget.select()}
        className="w-7 bg-transparent text-center outline-none placeholder:text-muted/60"
      />
      <button
        ref={pRef}
        type="button"
        aria-label={`Period: ${period}. Press to toggle.`}
        onClick={togglePeriod}
        onKeyDown={onPeriodKeyDown}
        className="ml-1 rounded px-1.5 py-0.5 text-sm font-medium text-ink/80 hover:bg-ink/5"
      >
        {period}
      </button>
    </div>
  );
}
