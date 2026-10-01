import { existsSync, readFileSync, writeFileSync } from 'node:fs';

const root = new URL('../', import.meta.url);
const read = (path) => JSON.parse(readFileSync(new URL(path, root), 'utf8'));
const accounts = read('pipeline/accounts.json').accounts;
// A fresh public clone has the sanitized directory, not private runtime state.
const activityHandles = existsSync(new URL('pipeline/data/account_activity.json', root))
  ? Object.keys(read('pipeline/data/account_activity.json'))
  : read('src/lib/public-clubs.json').activityHandles;
const directory = {
  accounts: accounts.map(({ handle, label, category }) => ({ handle, label, category })),
  activityHandles,
};
writeFileSync(new URL('src/lib/public-clubs.json', root), `${JSON.stringify(directory)}\n`);
