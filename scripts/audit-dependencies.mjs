import { spawnSync } from 'node:child_process';

// npm audit cannot ignore an advisory. Each entry here is one with no patched
// release that the depending packages accept, and that has been judged not to
// apply; remove it once they move to a fixed version.
const ACCEPTED = {
  // minimatch <11.0.1: glob-pattern amplification when optimizationLevel >= 2.
  // Only ESLint and its plugins use it, matching globs from this repository's
  // own lint config, never user input. eslint-plugin-react, -import and
  // -jsx-a11y need 3.x, which predates optimizationLevel and lacks the
  // vulnerable code; 11.x exports an object instead of the function they call,
  // so it can't be forced through overrides. typescript-eslint's 10.x copy
  // only matches projectService globs, which eslint.config.mjs doesn't set.
  'GHSA-g3hv-75wg-m249': 'minimatch fix is 11.x only, which ESLint plugins reject; dev tooling only',
};
const BLOCKING = new Set(['moderate', 'high', 'critical']);

const audit = spawnSync('npm', ['audit', '--json'], { encoding: 'utf8' });
const report = JSON.parse(audit.stdout || '{}');
if (!report.vulnerabilities) {
  console.error(audit.stderr || audit.stdout);
  process.exit(1);
}
// Packages listed only through a vulnerable dependency name no advisory of
// their own; each chain ends at an advisory object somewhere in the report.
const advisories = new Map();
for (const [name, entry] of Object.entries(report.vulnerabilities)) {
  for (const via of entry.via) {
    if (typeof via === 'object' && BLOCKING.has(via.severity)) {
      advisories.set(via.url.split('/').pop(), `${name}: ${via.title} (${via.url})`);
    }
  }
}
const blocking = [...advisories].filter(([id]) => !(id in ACCEPTED));
for (const [id, reason] of Object.entries(ACCEPTED)) {
  console.log(advisories.has(id)
    ? `Accepted ${id}: ${reason}`
    : `Accepted ${id} no longer appears; remove it from scripts/audit-dependencies.mjs`);
}
if (blocking.length) {
  for (const [, description] of blocking) console.error(description);
  process.exit(1);
}
console.log('No unaccepted moderate or higher advisories.');
