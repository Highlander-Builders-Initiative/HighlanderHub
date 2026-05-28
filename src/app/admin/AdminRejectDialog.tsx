"use client";

type AdminRejectDialogProps = {
  title: string;
  reason: string;
  onReasonChange: (reason: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
  isPending: boolean;
};

export function AdminRejectDialog({
  title,
  reason,
  onReasonChange,
  onCancel,
  onConfirm,
  isPending,
}: AdminRejectDialogProps) {
  return (
    <div
      className="fixed inset-0 bg-ink/35 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="reject-dialog-title"
    >
      <div className="bg-canvas w-full max-w-md rounded-xl border border-ink/10 p-6 shadow-card animate-scale-in">
        <header className="mb-4">
          <h3 id="reject-dialog-title" className="font-display text-lg font-semibold text-ink">
            Reject submission?
          </h3>
          <p className="text-xs text-muted font-sans mt-1">
            &ldquo;{title}&rdquo; will not be published. You can add an internal note
            below (optional).
          </p>
        </header>
        <label
          className="block text-[12px] font-sans text-muted mb-1.5"
          htmlFor="reject-reason"
        >
          Note (optional)
        </label>
        <textarea
          id="reject-reason"
          value={reason}
          onChange={(e) => onReasonChange(e.target.value)}
          rows={3}
          placeholder="e.g. duplicate event, missing details..."
          className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors resize-y font-sans leading-relaxed mb-4"
        />
        <div className="flex flex-col-reverse sm:flex-row gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={isPending}
            className="flex-1 min-h-10 border border-ink/10 hover:bg-ink/5 text-muted hover:text-ink text-xs font-semibold rounded-md transition-colors outline-none interactive-focus disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className="flex-1 min-h-10 bg-deep-coral hover:bg-deep-coral/90 text-canvas text-xs font-semibold rounded-md transition-colors outline-none interactive-focus disabled:opacity-50"
          >
            Reject submission
          </button>
        </div>
      </div>
    </div>
  );
}
