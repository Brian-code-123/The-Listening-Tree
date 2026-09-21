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

  it.each([
    'postgresql://localhost@evil.example.net/db', // "localhost" is only the user name
    'postgresql://u@localhost.evil.example.net/db', // look-alike host
    'postgresql://u@127.0.0.1.evil.example.net/db',
    'postgresql://u:pw@127.0.0.1@evil.example.net/db', // last @ wins
    'postgresql:///db?host=/var/run/postgresql', // no host: refused rather than guessed
  ])('refuses the look-alike %s', (url) => {
    expect(() => assertLocalDb(url)).toThrow();
  });

  it('accepts an upper-case LOCALHOST', () => {
    expect(assertLocalDb('postgresql://u@LOCALHOST:5432/db')).toContain('LOCALHOST');
  });

  it('gives a clear error for something that is not a URL', () => {
    expect(() => assertLocalDb('not a url')).toThrow(/not a valid URL/);
  });

  it('refuses an empty url', () => {
    expect(() => assertLocalDb('')).toThrow();
  });
});
