import { describe, expect, it } from 'vitest';
import { assertLocalDb } from '../support/env';

describe('assertLocalDb', () => {
  it.each([
    'postgresql://u@localhost:5432/db',
    'postgresql://u@127.0.0.1:5432/db',
    'postgresql://u@[::1]:5432/db',
  ])('allows %s', (url) => {
    expect(assertLocalDb(url)).toBe(url);
  });

  it.each([
    'postgresql://postgres:pw@db.qxruappgsrwjezjzrcnd.supabase.co:5432/postgres',
    'postgresql://postgres.x:pw@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres',
  ])('refuses %s', (url) => {
    expect(() => assertLocalDb(url)).toThrow(/not local/);
  });

  it('refuses an empty url', () => {
    expect(() => assertLocalDb('')).toThrow();
  });
});
