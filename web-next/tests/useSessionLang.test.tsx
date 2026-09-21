import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../app/lib/me', () => ({ fetchCurrentUser: vi.fn() }));
import { fetchCurrentUser } from '../app/lib/me';
import { useSessionLang } from '../app/lib/useSessionLang';

const mocked = vi.mocked(fetchCurrentUser);

describe('useSessionLang', () => {
  beforeEach(() => {
    mocked.mockReset();
  });

  it('starts as en', () => {
    mocked.mockReturnValue(new Promise(() => {}));
    expect(renderHook(() => useSessionLang()).result.current).toBe('en');
  });

  it('adopts the session language even when logged out', async () => {
    mocked.mockResolvedValue({ authenticated: false, lang: 'zh-HK' });
    const { result } = renderHook(() => useSessionLang());
    await waitFor(() => expect(result.current).toBe('zh-HK'));
  });

  it('stays en when /me fails', async () => {
    mocked.mockRejectedValue(new Error('network'));
    const { result } = renderHook(() => useSessionLang());
    await new Promise((r) => setTimeout(r, 20));
    expect(result.current).toBe('en');
  });
});
