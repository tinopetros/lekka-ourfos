import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { Lines } from '@/components/Lines';
import type { JournalEntry } from '@/lib/api/types';
import { useCan } from '@/lib/api/queries';
import { day } from '@/lib/format';
import { LINK } from '@/lib/styles';

// A journal entry as both its pages show it: where it stands, its ID and date, then its lines. Anything to do with
// it, e.g. going to it, sits to the right
export function EntrySummary({ e, live, action }: { e: JournalEntry; live: boolean; action?: ReactNode }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start gap-3">
        <dl className="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted-foreground">Status</dt>
          <dd>
            <Status e={e} live={live} />
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

// A mirror says what it undid, though Mifos-wise it's as live as any entry: its status is "live", its reverses the
// other. The entry it undid says what undid it
function Status({ e, live }: { e: JournalEntry; live: boolean }) {
  if (e.reverses) return <Linked to={e.reverses}>Reversal of</Linked>;
  if (e.reversed_by) return <Linked to={e.reversed_by}>Reversed by</Linked>;
  if (live) return <span className="font-medium text-emerald-700 dark:text-emerald-400">Live in Mifos</span>;
  return <span className="capitalize">{e.status ?? '—'}</span>;
}

function Linked({ to, children }: { to: string; children: ReactNode }) {
  const can = useCan();
  return (
    <>
      {children}{' '}
      {can('journal_entries:read') ? (
        <Link to={`/journal/${to}`} className={`font-mono ${LINK}`}>
          {to}
        </Link>
      ) : (
        <span className="font-mono">{to}</span>
      )}
    </>
  );
}
