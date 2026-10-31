import { Loader2, PencilLine, Plus, X } from 'lucide-react';
import { useRef, useState } from 'react';
import { Tip } from '@/components/Tip';
import { ConfirmContent } from '@/components/ConfirmContent';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { accountLabel as label, money } from '@/lib/format';
import type { JournalEntry } from '@/lib/api/types';
import { AccountPicker } from './AccountPicker';
import { useAccounts, type useCorrection } from './api';

type Side = 'DEBIT' | 'CREDIT';
// A line as it's being edited: the account picked, what it was named on the entry, and its amount as typed
type Row = { key: number; side: Side; glId?: number; shown?: string; amount: string };

export const CORRECT_TIP =
  'Posts a reversal to Mifos, then the corrected lines you set here, on the same date. The corrected entry is then the live one, and the requisition’s thread is told why.';

const cents = (n: number) => Math.round(n * 100);

let next = 0;
function rows(e: JournalEntry): Row[] {
  return e.lines.map((x) => ({
    key: next++,
    side: x.type ?? 'DEBIT',
    glId: x.glId ?? undefined,
    shown: label(x),
    amount: String(x.amount),
  }));
}

// Corrects a requisition's live entry: its mirror, then the lines set here. They start as the entry's own, and it
// posts only when each has an account Mifos lets it post to and debits equal credits
export function CorrectEntry({ e, correction }: { e: JournalEntry; correction: ReturnType<typeof useCorrection> }) {
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<Row[]>([]);
  const [reason, setReason] = useState('');
  // Once a correction's been tried, what's still in its way is said: the reason beside its box, the first of the rest
  // by the button
  const [tried, setTried] = useState(false);
  const why = useRef<HTMLTextAreaElement>(null);
  const accounts = useAccounts(e.tenant, open);
  const correcting = correction.isPending && !!correction.variables.lines;

  // Only an account of the tenant's: one the entry had that Mifos no longer takes manual entries on must be re-picked
  const known = new Map((accounts.data ?? []).map((a) => [a.glId, a]));
  const picked = lines.map((x) => ({
    ...x,
    to: x.glId === undefined ? undefined : known.get(x.glId),
    value: Number(x.amount),
  }));
  const total = (side: Side) => picked.filter((x) => x.side === side).reduce((n, x) => n + cents(x.value || 0), 0);
  const [debits, credits] = [total('DEBIT'), total('CREDIT')];
  const same =
    JSON.stringify(picked.map((x) => [x.side, x.to?.glId, cents(x.value)])) ===
    JSON.stringify(e.lines.map((x) => [x.type, x.glId, cents(x.amount)]));
  const missing = !reason.trim();
  const problems = [
    !picked.every((x) => x.to) && 'Pick an account for every line',
    !picked.every((x) => x.value > 0) && 'Give every line an amount over 0',
    !(picked.some((x) => x.side === 'DEBIT') && picked.some((x) => x.side === 'CREDIT')) &&
      'Have at least one debit and one credit',
    debits !== credits && 'Make debits equal credits',
    // A reason alone corrects nothing
    same && 'The journal entry hasn’t been corrected yet: change at least one line',
  ].filter((x) => x !== false);

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
              setTried(false);
              setOpen(true);
            }}
          >
            {correcting ? <Loader2 className="animate-spin" /> : <PencilLine />}
            {correcting ? 'Correcting…' : 'Correct journal entry'}
          </Button>
        </span>
      </Tip>
      <Dialog open={open} onOpenChange={setOpen}>
        <ConfirmContent className="gap-6 sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Correct journal entry</DialogTitle>
            <DialogDescription>
              Transaction <span className="text-foreground">{e.transaction_id}</span> will be reversed in Mifos, then
              these lines posted on the same date{e.tenant === 'demo' ? ', in demo' : ''}. Pick each line&apos;s account
              from Mifos&apos;s, by its name or GL code: only those that take manual entries are listed.
            </DialogDescription>
          </DialogHeader>
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
                <AccountPicker
                  accounts={accounts.data ?? []}
                  value={x.glId}
                  shown={x.shown}
                  loading={accounts.isPending}
                  onPick={(a) => {
                    set(x.key, { glId: a.glId });
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
                  setLines((ls) => [...ls, { key: next++, side: 'DEBIT', amount: '' }]);
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
            <Label htmlFor="correct-reason">
              Why it&apos;s corrected <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="correct-reason"
              ref={why}
              rows={3}
              placeholder="e.g. Booked to the wrong expense account"
              aria-invalid={tried && missing}
              value={reason}
              onChange={(ev) => {
                setReason(ev.target.value);
              }}
            />
            {tried && missing && (
              <p role="alert" className="text-sm text-destructive">
                A reason is needed to correct it.
              </p>
            )}
          </div>
          {tried && problems.length > 0 && (
            <p role="alert" className="text-sm text-destructive">
              {problems[0]}.
            </p>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              disabled={correction.isPending}
              onClick={() => {
                if (problems.length || missing) {
                  setTried(true);
                  if (missing) why.current?.focus();
                  return;
                }
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
        </ConfirmContent>
      </Dialog>
    </>
  );
}
