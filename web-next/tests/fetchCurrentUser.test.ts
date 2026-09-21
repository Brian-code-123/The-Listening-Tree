import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchCurrentUser } from '../app/lib/me';

const respond = (status: number, body: unknown) =>
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(body), { status }));

describe('fetchCurrentUser', () => {
  afterEach(() => vi.restoreAllMocks());

  // Regression pin: the logged-out login/register pages get their language from
  // the 401 body, so it must not be dropped.
  it('keeps the session language from a 401 (logged out)', async () => {
    respond(401, { authenticated: false, lang: 'zh-HK' });
    expect(await fetchCurrentUser()).toEqual({ authenticated: false, lang: 'zh-HK' });
  });

  it('tolerates a non-JSON 401 body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('<html>bad gateway</html>', { status: 401 }));
    expect(await fetchCurrentUser()).toEqual({ authenticated: false, lang: undefined });
  });

  it('returns the user for a 200', async () => {
    respond(200, { authenticated: true, email: 'a@b.c', lang: 'en' });
    expect((await fetchCurrentUser()).email).toBe('a@b.c');
  });

  it('throws on a server error', async () => {
    respond(500, {});
    await expect(fetchCurrentUser()).rejects.toThrow('/me fetch failed: 500');
  });
});
