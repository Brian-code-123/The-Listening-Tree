import { cleanupE2eUsers, closeDb } from '../support/db';

export default async function globalTeardown() {
  await cleanupE2eUsers();
  await closeDb();
}
