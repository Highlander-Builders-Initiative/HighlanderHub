export function Marquee({ text }: { text: string }) {
  // duplicate so the loop is seamless
  const items = Array.from({ length: 8 }, (_, i) => i);
  return (
    <div className="overflow-hidden border-y border-ink bg-ink text-bone py-2">
      <div className="flex animate-marquee whitespace-nowrap font-mono text-xs tracking-widest uppercase">
        {items.map((i) => (
          <span key={i} className="mx-8 inline-flex items-center gap-8">
            {text}
            <span aria-hidden>✦</span>
          </span>
        ))}
      </div>
    </div>
  );
}
