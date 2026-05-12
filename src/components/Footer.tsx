export function Footer() {
  return (
    <footer id="about" className="border-t border-line mt-12">
      <div className="mx-auto max-w-7xl px-6 py-12 grid gap-10 md:grid-cols-3">
        <div>
          <div className="flex items-center gap-2.5 mb-3">
            <span
              aria-hidden
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-highlander text-white font-display font-bold"
            >
              H
            </span>
            <span className="font-display text-lg font-semibold">
              Highlander Hub
            </span>
          </div>
          <p className="text-sm text-muted max-w-xs">
            A simple place to see everything happening at UC Riverside and
            around the city — without scrolling ten group chats.
          </p>
        </div>
        <div id="sources">
          <h3 className="text-sm font-semibold text-ink mb-3">Sources</h3>
          <ul className="space-y-1.5 text-sm text-muted">
            <li>Instagram (club accounts)</li>
            <li>Highlander Link</li>
            <li>events.ucr.edu</li>
            <li>Individual club sites</li>
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-ink mb-3">Status</h3>
          <p className="text-sm text-muted">
            Placeholder data — no live scrape yet.
          </p>
          <p className="text-sm text-muted mt-2">
            Built by a UCR student, for UCR students.
          </p>
        </div>
      </div>
      <div className="border-t border-line py-5 text-center text-xs text-muted">
        © {new Date().getFullYear()} Highlander Hub · Not affiliated with UCR
      </div>
    </footer>
  );
}
