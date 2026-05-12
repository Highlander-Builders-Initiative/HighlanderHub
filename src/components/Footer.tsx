export function Footer() {
  return (
    <footer className="border-t-4 border-double border-ink mt-20">
      <div className="mx-auto max-w-7xl px-6 py-10 grid gap-8 md:grid-cols-3">
        <div>
          <h3 className="font-display text-2xl mb-2">About</h3>
          <p className="font-body text-base text-ink/80">
            A bulletin for everything happening at UC Riverside and around the
            city. Pulled from Instagram, Highlander Link, UCR Events, and club
            websites.
          </p>
        </div>
        <div>
          <h3 className="font-display text-2xl mb-2">Sources</h3>
          <ul className="font-mono text-xs uppercase tracking-widest space-y-1">
            <li>· Instagram (club accounts)</li>
            <li>· Highlander Link</li>
            <li>· events.ucr.edu</li>
            <li>· Individual club sites</li>
          </ul>
        </div>
        <div>
          <h3 className="font-display text-2xl mb-2">Status</h3>
          <p className="font-mono text-xs uppercase tracking-widest text-ink/60">
            Placeholder data · No live scrape yet
          </p>
          <p className="font-body italic text-ink/60 mt-2">
            Built by a UCR student, for UCR students.
          </p>
        </div>
      </div>
      <div className="border-t border-ink/20 py-4 text-center font-mono text-[10px] uppercase tracking-widest text-ink/40">
        © {new Date().getFullYear()} The Highlander Daily · Not affiliated with UCR
      </div>
    </footer>
  );
}
