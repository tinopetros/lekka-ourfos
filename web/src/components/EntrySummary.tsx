import type { ReactNode } from 'react';
import { Lines } from '@/components/Lines';
import type { JournalEntry } from '@/lib/api/types';
import { day } from '@/lib/format';

// A journal entry as both its pages show it: where it stands, its ID and date, then its lines. Anything to do with
// it, e.g. going to it, sits to the right
export function EntrySummary({ e, live, action }: { e: JournalEntry; live: boolean; action?: ReactNode }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start gap-3">
        <dl className="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted-foreground">Status</dt>
          <dd>
            {live ? (
              <span className="font-medium text-emerald-700 dark:text-emerald-400">Live in Mifos</span>
            ) : (
              <span className="capitalize">{e.status ?? '—'}</span>
            )}
          </dd>
          <dt className="text-muted-foreground">Transaction ID</dt>
          <dd className="font-mono">{e.transaction_id}</dd>
          <dt className="text-muted-foreground">Transaction date</dt>
          <dd>{day(e.transaction_date)}</dd>
        </dl>
        {action && <div className="ml-auto flex gap-2">{action}</div>}
      </div>
      <Lines lines={e.lines} currency={e.currency} />
    </div>
  );
}
