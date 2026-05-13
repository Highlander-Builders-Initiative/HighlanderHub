export function Footer() {
  return (
    <footer id="about" className="mt-16 border-t border-ink/10">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-2">
        <div>
          <p className="font-display text-xl font-semibold tracking-[-0.04em] text-ink">
            highlander<span className="text-muted">/</span>hub
          </p>
          <p className="mt-3 max-w-md text-sm text-muted">
            A simple place to see what&rsquo;s happening at UC Riverside and
            around the city, without scrolling ten group chats.
          </p>
        </div>
        <div className="md:text-right">
          <h3 className="mb-3 text-sm font-semibold text-ink">Status</h3>
          <p className="text-sm text-muted">
            Placeholder data. No live scrape yet.
          </p>
          <p className="mt-2 text-sm text-muted">
            Built by a UCR student, for UCR students.
          </p>
        </div>
      </div>
      <div className="border-t border-ink/10 py-5 text-center text-xs text-muted">
        © {new Date().getFullYear()} Highlander Hub · Not affiliated with UCR
      </div>
    </footer>
  );
}
