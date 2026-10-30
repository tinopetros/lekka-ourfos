import { Loader2, PencilLine, Plus, X } from 'lucide-react';
import { useId, useState } from 'react';
import { Tip } from '@/components/Tip';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { money } from '@/lib/format';
import type { components } from '@/lib/api/schema';
import type { JournalEntry } from '@/lib/api/types';
import { useAccounts, type useCorrection } from './api';

type Account = components['schemas']['Account'];
type Side = 'DEBIT' | 'CREDIT';
// A line as it's being edited: its account picked by what's typed, its amount as typed
type Row = { key: number; side: Side; account: string; amount: string };

export const CORRECT_TIP =
  'Posts a reversal to Mifos, then the corrected lines you set here, on the same date. The corrected entry is then the live one, and the requisition’s thread is told why.';

// Name first, as Mifos lists them, and what's searched by most
const label = (a: { glCode?: string | null; name: string }) => `${a.name} (${a.glCode})`;
const cents = (n: number) => Math.round(n * 100);

let next = 0;
function rows(e: JournalEntry): Row[] {
  return e.lines.map((x) => ({
    key: next++,
    side: x.type ?? 'DEBIT',
    account: label(x),
    amount: String(x.amount),
  }));
}

// Corrects a requisition's live entry: its mirror, then the lines set here. They start as the entry's own, and it
// posts only when each has an account Mifos lets it post to and debits equal credits
export function CorrectEntry({ e, correction }: { e: JournalEntry; correction: ReturnType<typeof useCorrection> }) {
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<Row[]>([]);
  const [reason, setReason] = useState('');
  const accounts = useAccounts(e.tenant, open);
  const list = useId();
  const correcting = correction.isPending && !!correction.variables.lines;

  // Only an account of the tenant's: picked from the list, or typed as its GL code or name. Anything else is refused
  const known = new Map(
    (accounts.data ?? []).flatMap((a) => [
      [label(a), a],
      [a.glCode, a],
      [a.name.toLowerCase(), a],
    ]),
  );
  const find = (typed: string) => known.get(typed.trim()) ?? known.get(typed.trim().toLowerCase());
  const picked = lines.map((x) => ({ ...x, to: find(x.account), value: Number(x.amount) }));
  const total = (side: Side) => picked.filter((x) => x.side === side).reduce((n, x) => n + cents(x.value || 0), 0);
  const [debits, credits] = [total('DEBIT'), total('CREDIT')];
  const valid = picked.every((x) => x.to && x.value > 0);
  const sides = picked.some((x) => x.side === 'DEBIT') && picked.some((x) => x.side === 'CREDIT');
  const same =
    JSON.stringify(picked.map((x) => [x.side, x.to?.glId, cents(x.value)])) ===
    JSON.stringify(e.lines.map((x) => [x.type, x.glId, cents(x.amount)]));
  const ready = valid && sides && debits === credits && debits > 0 && !same && !!reason.trim();

  const set = (key: number, change: Partial<Row>) => {
    setLines((ls) => ls.map((x) => (x.key === key ? { ...x, ...change } : x)));
  };
  const side = (s: Side) => picked.flatMap((x) => (x.side === s && x.to ? [{ glId: x.to.glId, amount: x.value }] : []));

  return (
    <>
      <Tip label={CORRECT_TIP} delay={300}>
        <span>
          <Button
            variant="outline"
            size="sm"
            disabled={correction.isPending}
            onClick={() => {
              setLines(rows(e));
              setReason('');
              setOpen(true);
            }}
          >
            {correcting ? <Loader2 className="animate-spin" /> : <PencilLine />}
            {correcting ? 'Correcting…' : 'Correct journal entry'}
          </Button>
        </span>
      </Tip>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="gap-6 sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Correct journal entry</DialogTitle>
            <DialogDescription>
              Transaction <span className="text-foreground">{e.transaction_id}</span> will be reversed in Mifos, then
              these lines posted on the same date{e.tenant === 'demo' ? ', in demo' : ''}. Search an account by its name
              or GL code: only Mifos accounts that take manual entries are accepted.
            </DialogDescription>
          </DialogHeader>
          <datalist id={list}>
            {accounts.data?.map((a: Account) => (
              <option key={a.glId} value={label(a)} />
            ))}
          </datalist>
          <div className="space-y-3">
            {picked.map((x) => (
              <div key={x.key} className="flex items-center gap-2">
                <Select
                  value={x.side}
                  onValueChange={(v) => {
                    set(x.key, { side: v as Side });
                  }}
                >
                  <SelectTrigger className="w-24 shrink-0" aria-label="Debit or credit">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="DEBIT">Debit</SelectItem>
                    <SelectItem value="CREDIT">Credit</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  list={list}
                  aria-label="Account"
                  placeholder={accounts.isPending ? 'Loading accounts…' : 'Account name or GL code'}
                  aria-invalid={!!x.account && !x.to && !accounts.isPending}
                  className="min-w-0 flex-1"
                  value={x.account}
                  onChange={(ev) => {
                    set(x.key, { account: ev.target.value });
                  }}
                  onBlur={() => {
                    if (x.to) set(x.key, { account: label(x.to) });
                  }}
                />
                <Input
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  aria-label="Amount"
                  aria-invalid={!!x.amount && !(x.value > 0)}
                  className="w-28 shrink-0 text-right"
                  value={x.amount}
                  onChange={(ev) => {
                    set(x.key, { amount: ev.target.value });
                  }}
                />
                <Tip label="Remove line">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Remove line"
                    disabled={lines.length <= 2}
                    onClick={() => {
                      setLines((ls) => ls.filter((l) => l.key !== x.key));
                    }}
                  >
                    <X />
                  </Button>
                </Tip>
              </div>
            ))}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-2 text-sm">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setLines((ls) => [...ls, { key: next++, side: 'DEBIT', account: '', amount: '' }]);
                }}
              >
                <Plus /> Add line
              </Button>
              <span className="ml-auto text-muted-foreground">
                Debits <span className="text-foreground tabular-nums">{money(debits / 100, e.currency ?? 'USD')}</span>
                {' · '}Credits{' '}
                <span className="text-foreground tabular-nums">{money(credits / 100, e.currency ?? 'USD')}</span>
              </span>
            </div>
            {debits !== credits && (
              <p className="text-right text-sm text-destructive">
                Off by {money(Math.abs(debits - credits) / 100, e.currency ?? 'USD')}
              </p>
            )}
            {accounts.isError && (
              <p className="text-sm text-destructive">
                Couldn&apos;t read Mifos&apos;s accounts: {accounts.error.message}
              </p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="correct-reason">Why it&apos;s corrected</Label>
            <Textarea
              id="correct-reason"
              rows={3}
              value={reason}
              onChange={(ev) => {
                setReason(ev.target.value);
              }}
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              disabled={!ready}
              onClick={() => {
                setOpen(false);
                correction.mutate({
                  transaction_id: e.transaction_id,
                  reason: reason.trim(),
                  lines: { debit: side('DEBIT'), credit: side('CREDIT') },
                });
              }}
            >
              Correct journal entry
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
