import { useState } from 'react';
import { useAccounts, type CorrectedLines } from './api';

export type Side = 'DEBIT' | 'CREDIT';
// A line as it's being edited: the account picked, what it was named on the entry, and its amount as typed
export type Row = { key: number; side: Side; glId?: number; shown?: string; amount: string };

export const cents = (n: number) => Math.round(n * 100);

let next = 0;
export const row = (r: Omit<Row, 'key'>): Row => ({ ...r, key: next++ });

/** The lines of an entry being set, against the tenant's accounts: what's picked, its totals, and what's still in the
 * way of posting them. Accounts are read once the dialog opens */
export function useEntryLines(tenant: string | null | undefined, open: boolean) {
  const [lines, setLines] = useState<Row[]>([]);
  const accounts = useAccounts(tenant, open);
  // Only an account of the tenant's: one the entry had that Mifos no longer takes manual entries on must be re-picked
  const known = new Map((accounts.data ?? []).map((a) => [a.glId, a]));
  const picked = lines.map((x) => ({
    ...x,
    to: x.glId === undefined ? undefined : known.get(x.glId),
    value: Number(x.amount),
  }));
  const total = (side: Side) => picked.filter((x) => x.side === side).reduce((n, x) => n + cents(x.value || 0), 0);
  const [debits, credits] = [total('DEBIT'), total('CREDIT')];
  const problems = [
    !picked.every((x) => x.to) && 'Pick an account for every line',
    !picked.every((x) => x.value > 0) && 'Give every line an amount over 0',
    !(picked.some((x) => x.side === 'DEBIT') && picked.some((x) => x.side === 'CREDIT')) &&
      'Have at least one debit and one credit',
    debits !== credits && 'Make debits equal credits',
  ].filter((x) => x !== false);
  const side = (s: Side) => picked.flatMap((x) => (x.side === s && x.to ? [{ glId: x.to.glId, amount: x.value }] : []));
  const sides = (): CorrectedLines => ({ debit: side('DEBIT'), credit: side('CREDIT') });
  return { lines, setLines, accounts, picked, debits, credits, problems, sides };
}
