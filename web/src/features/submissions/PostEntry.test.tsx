import { fireEvent, render, screen, within } from '@testing-library/react';
import { vi } from 'vitest';
import { TooltipProvider } from '@/components/ui/tooltip';
import type { components } from '@/lib/api/schema';
import { PostEntry } from './PostEntry';
import type { useCorrection } from './api';

vi.mock('./api', () => ({
  useAccounts: () => ({ data: [], isPending: false, isError: false }),
}));

const POSTING: components['schemas']['Posting'] = {
  reference: 'REQ-7',
  transaction_date: '2026-10-05',
  comments: 'Subject: Requisition Approval Request Form - City parking - #7. Response number: 7.',
  tenant: null,
};

function open(posting = POSTING) {
  const mutate = vi.fn();
  const correction = { isPending: false, mutate } as unknown as ReturnType<typeof useCorrection>;
  render(
    <TooltipProvider>
      <PostEntry posting={posting} correction={correction} />
    </TooltipProvider>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Post journal entry' }));
  return { dialog: screen.getByRole('dialog'), mutate };
}

test('it starts filed as Lekkai would have, with an empty debit and credit', () => {
  const { dialog } = open();
  expect(within(dialog).getByLabelText(/Reference number/)).toHaveValue('REQ-7');
  expect(within(dialog).getByLabelText(/Transaction date/)).toHaveValue('2026-10-05');
  expect(within(dialog).getByLabelText(/Comments in Mifos/)).toHaveValue(POSTING.comments);
  expect(within(dialog).getAllByLabelText('Amount')).toHaveLength(2);
  expect(within(dialog).queryByText(/reason/i)).not.toBeInTheDocument();
});

test('what the requisition lacks is asked for, and nothing posts until it is', () => {
  const { dialog, mutate } = open({ ...POSTING, transaction_date: null });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Post journal entry' }));
  expect(within(dialog).getByRole('alert')).toHaveTextContent('Give its transaction date.');
  expect(mutate).not.toHaveBeenCalled();
});

test('lines without accounts are refused', () => {
  const { dialog, mutate } = open();
  fireEvent.click(within(dialog).getByRole('button', { name: 'Post journal entry' }));
  expect(within(dialog).getByRole('alert')).toHaveTextContent('Pick an account for every line.');
  expect(mutate).not.toHaveBeenCalled();
});
