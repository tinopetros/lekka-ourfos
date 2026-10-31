import { Plus, X } from 'lucide-react';
import { Tip } from '@/components/Tip';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { money } from '@/lib/format';
import { AccountPicker } from './AccountPicker';
import { row, type Row, type Side, type useEntryLines } from './lines';

/** Each line's side, account and amount, a line added or taken away, and debits and credits as they stand */
export function EntryLines({
  editor,
  currency,
}: {
  editor: ReturnType<typeof useEntryLines>;
  currency: string | null | undefined;
}) {
  const { lines, setLines, accounts, picked, debits, credits } = editor;
  const set = (key: number, change: Partial<Row>) => {
    setLines((ls) => ls.map((x) => (x.key === key ? { ...x, ...change } : x)));
  };
  return (
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
            setLines((ls) => [...ls, row({ side: 'DEBIT', amount: '' })]);
          }}
        >
          <Plus /> Add line
        </Button>
        <span className="ml-auto text-muted-foreground">
          Debits <span className="text-foreground tabular-nums">{money(debits / 100, currency ?? 'USD')}</span>
          {' · '}Credits <span className="text-foreground tabular-nums">{money(credits / 100, currency ?? 'USD')}</span>
        </span>
      </div>
      {debits !== credits && (
        <p className="text-right text-sm text-destructive">
          Off by {money(Math.abs(debits - credits) / 100, currency ?? 'USD')}
        </p>
      )}
      {accounts.isError && (
        <p className="text-sm text-destructive">Couldn&apos;t read Mifos&apos;s accounts: {accounts.error.message}</p>
      )}
    </div>
  );
}
