type Props = {
  items?: string[];
};

const DEFAULTS = [
  "Updated daily",
  "Free food alerts",
  "Club nights",
  "Career fairs",
  "Off-campus picks",
];

export function Marquee({ items = DEFAULTS }: Props) {
  return (
    <div className="border-b border-ink/10 bg-canvas">
      <div className="mx-auto flex max-w-7xl items-center gap-4 overflow-x-auto whitespace-nowrap px-4 py-2 text-sm text-muted sm:px-6">
        <span
          className="relative inline-flex h-2 w-2 shrink-0"
          aria-hidden="true"
        >
          <span className="absolute inline-flex h-full w-full rounded-full bg-leaf opacity-60 animate-ping" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-leaf" />
        </span>
        <ul className="flex items-center gap-x-5">
          {items.map((item, i) => (
            <li key={item} className="flex items-center gap-3">
              {i > 0 && <span className="text-ink/20">·</span>}
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
