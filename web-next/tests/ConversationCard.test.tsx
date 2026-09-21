import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../app/lib/api', async (orig) => ({
  ...(await orig<typeof import('../app/lib/api')>()),
  deleteConversation: vi.fn(),
}));
import { deleteConversation } from '../app/lib/api';
import ConversationCard from '../app/history/components/ConversationCard';

const conversation = { id: 7, title: 'Hello', updated_at: '2030-01-01 10:00', pinned: false, tag: null };
const translations = { delete_conversation: 'Delete', delete_conversation_confirm: 'Sure?' };
const mockedDelete = vi.mocked(deleteConversation);

function setup() {
  const onDelete = vi.fn();
  render(
    <ConversationCard conversation={conversation} translations={translations} onUpdate={vi.fn()} onDelete={onDelete} activeFilter="all" />,
  );
  return { onDelete, button: screen.getByTitle('Delete') };
}

describe('ConversationCard delete', () => {
  beforeEach(() => {
    mockedDelete.mockReset();
    vi.restoreAllMocks();
  });

  it('does nothing when the user cancels the confirm dialog', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { onDelete, button } = setup();
    fireEvent.click(button);
    expect(mockedDelete).not.toHaveBeenCalled();
    expect(onDelete).not.toHaveBeenCalled();
  });

  it('shows the translated confirmation text', () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    fireEvent.click(setup().button);
    expect(confirm).toHaveBeenCalledWith('Sure?');
  });

  it('deletes and notifies the parent when confirmed', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    mockedDelete.mockResolvedValue({ deleted: true });
    const { onDelete, button } = setup();
    fireEvent.click(button);
    await waitFor(() => expect(onDelete).toHaveBeenCalledWith(7));
    expect(mockedDelete).toHaveBeenCalledWith(7);
  });

  it('re-enables the button and keeps the card when the request fails', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    mockedDelete.mockRejectedValue(new Error('500'));
    const { onDelete, button } = setup();
    fireEvent.click(button);
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    expect(onDelete).not.toHaveBeenCalled();
  });

  it('ignores a second click while a delete is in flight', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    mockedDelete.mockReturnValue(new Promise(() => {}));
    const { button } = setup();
    fireEvent.click(button);
    fireEvent.click(button);
    expect(mockedDelete).toHaveBeenCalledTimes(1);
  });
});
