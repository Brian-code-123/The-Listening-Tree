import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const replace = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace }) }));
vi.mock('../app/lib/auth', () => ({ logout: vi.fn() }));
import { logout } from '../app/lib/auth';
import LogoutButton from '../app/components/LogoutButton';

const mocked = vi.mocked(logout);

describe('LogoutButton', () => {
  beforeEach(() => {
    mocked.mockReset();
    replace.mockReset();
  });

  it('is a button, not a link, so a page cannot trigger it with a GET', () => {
    render(<LogoutButton className="btn" ariaLabel="Logout">Logout</LogoutButton>);
    const el = screen.getByRole('button', { name: 'Logout' });
    expect(el.tagName).toBe('BUTTON');
    expect(el.getAttribute('href')).toBeNull();
  });

  it('signs out on the server, then goes to the login page', async () => {
    mocked.mockResolvedValue(undefined);
    render(<LogoutButton className="btn">Logout</LogoutButton>);
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/login'));
    expect(mocked).toHaveBeenCalledTimes(1);
  });

  it('stays on the page when the server could not be reached, so nobody believes they are signed out', async () => {
    mocked.mockRejectedValue(new Error('network'));
    render(<LogoutButton className="btn">Logout</LogoutButton>);
    const button = screen.getByRole('button');
    fireEvent.click(button);
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    expect(replace).not.toHaveBeenCalled();
  });

  it('ignores a second click while the first is in flight', async () => {
    let finish: () => void = () => {};
    mocked.mockReturnValue(new Promise<void>((resolve) => { finish = resolve; }));
    render(<LogoutButton className="btn">Logout</LogoutButton>);
    const button = screen.getByRole('button');
    fireEvent.click(button);
    fireEvent.click(button);
    expect(mocked).toHaveBeenCalledTimes(1);
    finish();
    await waitFor(() => expect(replace).toHaveBeenCalledTimes(1));
  });
});
