import { assertLocalDb, e2eDbUrl } from '../support/env';
import { cleanupE2eUsers, closeDb } from '../support/db';

export default async function globalSetup() {
  assertLocalDb(e2eDbUrl());
  try {
    await cleanupE2eUsers();
  } catch (err) {
    throw new Error(
      `Cannot reach the e2e database (${(err as Error).message}). ` +
        'Run `npm run e2e:db` once to create and migrate listening_tree_e2e (in CI the Postgres service does this).',
    );
  } finally {
    await closeDb();
  }
}
