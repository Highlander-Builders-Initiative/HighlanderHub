import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, copyFileSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { test } from 'node:test';

test('a public clone generates its directory without private pipeline activity', () => {
  const root = mkdtempSync(join(tmpdir(), 'highlander-public-'));
  try {
    for (const path of ['scripts', 'pipeline', 'src/lib']) mkdirSync(join(root, path), { recursive: true });
    for (const path of ['scripts/generate-public-clubs.mjs', 'pipeline/accounts.json', 'src/lib/public-clubs.json']) {
      copyFileSync(new URL(`../${path}`, import.meta.url), join(root, path));
    }
    const before = readFileSync(join(root, 'src/lib/public-clubs.json'), 'utf8');
    execFileSync(process.execPath, [join(root, 'scripts/generate-public-clubs.mjs')]);
    assert.deepEqual(JSON.parse(readFileSync(join(root, 'src/lib/public-clubs.json'), 'utf8')), JSON.parse(before));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
