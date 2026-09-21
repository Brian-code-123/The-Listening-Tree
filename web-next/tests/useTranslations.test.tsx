import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useTranslations } from '../app/lib/i18n';

describe('useTranslations', () => {
  it('defaults to English', async () => {
    const { result } = renderHook(() => useTranslations());
    await waitFor(() => expect(result.current.t('sign_in', 'FALLBACK')).toBe('Sign In'));
  });

  it('follows the lang it is given', async () => {
    const { result } = renderHook(() => useTranslations('zh-HK'));
    await waitFor(() => expect(result.current.t('sign_in', 'FALLBACK')).toBe('登入'));
  });

  it('re-fetches when lang changes', async () => {
    const { result, rerender } = renderHook(({ lang }) => useTranslations(lang), { initialProps: { lang: 'en' } });
    await waitFor(() => expect(result.current.t('sign_in', 'x')).toBe('Sign In'));
    rerender({ lang: 'zh-HK' });
    await waitFor(() => expect(result.current.t('sign_in', 'x')).toBe('登入'));
  });

  it('falls back for an unknown key', async () => {
    const { result } = renderHook(() => useTranslations('en'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.t('definitely_not_a_key', 'my fallback')).toBe('my fallback');
  });
});
