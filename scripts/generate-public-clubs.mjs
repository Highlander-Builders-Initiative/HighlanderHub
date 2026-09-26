import { readFileSync, writeFileSync } from 'node:fs';

const root = new URL('../', import.meta.url);
const read = (path) => JSON.parse(readFileSync(new URL(path, root), 'utf8'));
const accounts = read('pipeline/accounts.json').accounts;
const activity = read('pipeline/data/account_activity.json');
const directory = {
  accounts: accounts.map(({ handle, label, category }) => ({ handle, label, category })),
  activityHandles: Object.keys(activity),
};
writeFileSync(new URL('src/lib/public-clubs.json', root), `${JSON.stringify(directory)}\n`);
