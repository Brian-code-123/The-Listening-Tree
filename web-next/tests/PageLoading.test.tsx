import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import PageLoading from '../app/components/PageLoading';

describe('PageLoading', () => {
  it('shows a spinner inside the test-id root', () => {
    const { getByTestId } = render(<PageLoading />);
    expect(getByTestId('page-loading').querySelector('i.fa-spinner')).not.toBeNull();
  });

  it('is light by default and dark when the saved theme is dark', () => {
    expect(render(<PageLoading />).getByTestId('page-loading').getAttribute('data-theme')).toBe('light');
    localStorage.setItem('theme', 'dark');
    expect(render(<PageLoading />).getAllByTestId('page-loading').at(-1)?.getAttribute('data-theme')).toBe('dark');
  });
});
