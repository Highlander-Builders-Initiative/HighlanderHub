import { spawnSync } from 'node:child_process';

// npm audit cannot ignore an advisory. Each entry here is one with no patched
// release that has been judged not to apply; remove it once a fix ships.
const ACCEPTED = {
  // braces <=3.0.3 (every release): stack exhaustion from deeply nested
  // patterns. Reached only through tailwindcss and eslint-config-next, which
  // expand globs from this repository's own config, never user input.
  'GHSA-vfj7-8cjw-p6xm': 'braces has no patched release; dev tooling only',
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
