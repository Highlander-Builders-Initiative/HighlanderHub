"use client";

import { useRef } from "react";
import type { UploadStatus } from "./use-flyer-upload";

export function FlyerUpload({
  status,
  isUrlOpen,
  onFile,
  onClear,
  onToggleUrl,
}: {
  status: UploadStatus;
  isUrlOpen: boolean;
  onFile: (file: File) => void | Promise<void>;
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
          if (file) void onFile(file);
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
        <span aria-hidden="true" className="text-ink/20">
          ·
        </span>
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
