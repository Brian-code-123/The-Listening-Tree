import pg from 'pg';
import { assertLocalDb, e2eDbUrl } from './env';

let pool: pg.Pool | undefined;

function getPool(): pg.Pool {
  if (!pool) pool = new pg.Pool({ connectionString: assertLocalDb(e2eDbUrl()), max: 4 });
  return pool;
}

export const query = (sql: string, params: unknown[] = []) => getPool().query(sql, params);

export async function closeDb() {
  if (pool) {
    await pool.end();
    pool = undefined;
  }
}

// The backend compares expires_at against Python's *local* datetime.now()
// string, so seed local wall-clock time (not the DB's now()) to avoid a
// timezone mismatch between the DB session and the app process.
function localTs(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

// Limiter keys look like "<bucket>:<client ip>". Clear everything except the
// reserved 203.0.113.x (TEST-NET-3) addresses, which the rate-limit test uses
// as its own private counters, so parallel workers resetting between tests
// can't wipe that test's counter mid-run.
export async function resetRateLimits() {
  await query("DELETE FROM rate_limit_events WHERE key NOT LIKE '%:203.0.113.%'");
}

export async function clearRateLimitKey(key: string) {
  await query('DELETE FROM rate_limit_events WHERE key = $1', [key]);
}

export async function rateLimitCount(key: string): Promise<number> {
  const res = await query('SELECT COALESCE(SUM(count), 0) AS n FROM rate_limit_events WHERE key = $1', [key]);
  return Number(res.rows[0].n);
}

export async function seedVerificationCode(email: string, code = '123456') {
  const now = new Date();
  await query(
    'INSERT INTO email_verifications (email, code, expires_at, created_at) VALUES ($1, $2, $3, $4)',
    [email, code, localTs(new Date(now.getTime() + 10 * 60_000)), localTs(now)],
  );
}

const USER_TABLES = ['reminders', 'chat_history', 'conversations', 'preferences'];

async function deleteWhere(userFilter: string, params: unknown[]) {
  for (const table of USER_TABLES) {
    await query(`DELETE FROM ${table} WHERE user_id IN (SELECT id FROM users WHERE ${userFilter})`, params);
  }
  await query(`DELETE FROM email_verifications WHERE ${userFilter}`, params);
  await query(`DELETE FROM users WHERE ${userFilter}`, params);
}

export async function deleteUser(email: string) {
  await deleteWhere('LOWER(email) = LOWER($1)', [email]);
}

export async function cleanupE2eUsers() {
  await deleteWhere("email LIKE 'e2e\\_%@example.com'", []);
}
