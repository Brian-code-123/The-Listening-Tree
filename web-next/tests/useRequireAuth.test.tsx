import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const replace = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace }) }));
vi.mock('../app/lib/me', () => ({ fetchCurrentUser: vi.fn() }));
import { fetchCurrentUser } from '../app/lib/me';
import { useRequireAuth } from '../app/lib/useRequireAuth';

const mocked = vi.mocked(fetchCurrentUser);

describe('useRequireAuth', () => {
  beforeEach(() => {
    mocked.mockReset();
    replace.mockReset();
  });

  it('exposes the user and does not redirect when logged in', async () => {
    mocked.mockResolvedValue({ authenticated: true, display_name: 'Ann' });
    const { result } = renderHook(() => useRequireAuth());
    await waitFor(() => expect(result.current.checking).toBe(false));
    expect(result.current.user?.display_name).toBe('Ann');
    expect(replace).not.toHaveBeenCalled();
  });

  it('routes to /login client-side when logged out, instead of reloading the document', async () => {
    mocked.mockResolvedValue({ authenticated: false });
    const { result } = renderHook(() => useRequireAuth());
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/login'));
    expect(result.current.user).toBeNull();
  });

  it('routes to /login when /me cannot be reached', async () => {
    mocked.mockRejectedValue(new Error('network'));
    renderHook(() => useRequireAuth());
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/login'));
  });

  it('does a full navigation when the API lives on another origin (local dev)', async () => {
    vi.resetModules();
    vi.stubEnv('NEXT_PUBLIC_API_BASE', 'http://localhost:5000');
    const assign = vi.fn();
    const original = window.location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { set href(v: string) { assign(v); } },
    });
    try {
      const { fetchCurrentUser: freshMe } = await import('../app/lib/me');
      vi.mocked(freshMe).mockResolvedValue({ authenticated: false });
      const { useRequireAuth: freshHook } = await import('../app/lib/useRequireAuth');
      renderHook(() => freshHook());
      await waitFor(() => expect(assign).toHaveBeenCalledWith('http://localhost:5000/login'));
      expect(replace).not.toHaveBeenCalled();
    } finally {
      Object.defineProperty(window, 'location', { configurable: true, value: original });
      vi.unstubAllEnvs();
    }
  });
});
