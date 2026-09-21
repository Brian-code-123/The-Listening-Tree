import os from 'node:os';

const SAFE_HOSTS = new Set(['localhost', '127.0.0.1', '::1']);

export function assertLocalDb(url: string): string {
  if (!url) throw new Error('No e2e DATABASE_URL resolved');
  const host = new URL(url).hostname.replace(/^\[|\]$/g, '').toLowerCase();
  if (!SAFE_HOSTS.has(host)) {
    throw new Error(
      `e2e refuses to run: DB host "${host}" is not local (${[...SAFE_HOSTS].join(', ')}). ` +
        'Check E2E_DATABASE_URL — it must never point at production.',
    );
  }
  return url;
}

export function e2eDbUrl(): string {
  return (
    process.env.E2E_DATABASE_URL ||
    `postgresql://${os.userInfo().username}@127.0.0.1:5432/listening_tree_e2e?sslmode=disable`
  );
}
