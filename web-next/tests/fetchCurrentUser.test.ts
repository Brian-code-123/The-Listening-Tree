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

  // Every page mounts a few components that each want /me at the same moment
  // (auth gate, the site-wide reminder alarm, ...). On serverless each request
  // can cold-start its own function instance, so overlapping calls share one.
  it('shares one request between overlapping callers', async () => {
    const spy = respond(401, { authenticated: false, lang: 'en' });
    const [a, b, c] = await Promise.all([fetchCurrentUser(), fetchCurrentUser(), fetchCurrentUser()]);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(a).toEqual(b);
    expect(b).toEqual(c);
  });

  it('does not cache once a request has settled (login/logout must be seen)', async () => {
    const spy = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({ authenticated: false, lang: 'en' }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ authenticated: true, email: 'a@b.c' }), { status: 200 }));
    expect((await fetchCurrentUser()).authenticated).toBe(false);
    expect((await fetchCurrentUser()).authenticated).toBe(true);
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it('a failed request does not poison later calls', async () => {
    const spy = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response('{}', { status: 500 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ authenticated: true }), { status: 200 }));
    await expect(fetchCurrentUser()).rejects.toThrow('500');
    expect((await fetchCurrentUser()).authenticated).toBe(true);
    expect(spy).toHaveBeenCalledTimes(2);
  });
});
