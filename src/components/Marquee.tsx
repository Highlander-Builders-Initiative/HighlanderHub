type Props = {
  items?: string[];
};

export function Marquee({ items }: Props) {
  const defaults = items ?? [
    "Updated daily",
    "Free food alerts",
    "Club nights",
    "Career fairs",
    "Off-campus picks",
  ];

  return (
    <div className="border-b border-line bg-surface">
      <div className="mx-auto max-w-7xl px-6 py-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted">
        <span className="inline-flex items-center gap-2 text-ink font-medium">
          <span className="relative flex h-2 w-2" aria-hidden="true">
            <span className="absolute inline-flex h-full w-full rounded-full bg-leaf opacity-60 animate-ping" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-leaf" />
          </span>
          Live
        </span>
        {defaults.map((item, i) => (
          <span key={item} className="inline-flex items-center gap-3">
            <span aria-hidden className="text-line">·</span>
            <span>{item}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
