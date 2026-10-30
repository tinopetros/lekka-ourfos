import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { Lines } from '@/components/Lines';
import type { JournalEntry } from '@/lib/api/types';
import { useCan } from '@/lib/api/queries';
import { day } from '@/lib/format';
import { LINK } from '@/lib/styles';

// A journal entry as both its pages show it: where it stands, its ID, date, reference and comments, then its lines.
// Anything to do with it, e.g. going to it, sits top right
export function EntrySummary({
  e,
  live,
  titled = false,
  action,
}: {
  e: JournalEntry;
  live: boolean;
  // Its transaction ID on top, a little bigger: for a list of them, where nothing else names each
  titled?: boolean;
  action?: ReactNode;
}) {
  return (
    <div className="space-y-3">
      {(titled || action) && (
        <div className="flex flex-wrap items-center gap-3">
          {titled && (
            <p className="flex items-baseline gap-2">
              <span className="text-sm text-muted-foreground">Transaction ID</span>
              <span className="text-base font-semibold">{e.transaction_id}</span>
            </p>
          )}
          {action && <div className="ml-auto flex gap-2">{action}</div>}
        </div>
      )}
      <dl className="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Status</dt>
        <dd>
          <Status e={e} live={live} />
        </dd>
        {!titled && (
          <>
            <dt className="text-muted-foreground">Transaction ID</dt>
            <dd>{e.transaction_id}</dd>
          </>
        )}
        <dt className="text-muted-foreground">Transaction date</dt>
        <dd>{day(e.transaction_date)}</dd>
        {e.reference_number && (
          <>
            <dt className="text-muted-foreground">Reference number</dt>
            <dd>{e.reference_number}</dd>
          </>
        )}
        {e.comments && (
          <>
            <dt className="text-muted-foreground">Comments</dt>
            <dd>{e.comments}</dd>
          </>
        )}
      </dl>
      <Lines lines={e.lines} currency={e.currency} />
    </div>
  );
}

// A mirror says what it undid, though Mifos-wise it's as live as any entry: its status is "live", its reverses the
// other. The entry it undid says what undid it
function Status({ e, live }: { e: JournalEntry; live: boolean }) {
  if (e.reverses) return <Linked to={e.reverses}>Reversal of</Linked>;
  if (e.reversed_by) return <Linked to={e.reversed_by}>Reversed by</Linked>;
  if (live)
    return (
      <span className="font-medium text-emerald-700 dark:text-emerald-400">
        Live in Mifos{e.tenant === 'demo' && <span className="font-normal text-muted-foreground"> (demo)</span>}
      </span>
    );
  return <span className="capitalize">{e.status ?? '—'}</span>;
}

function Linked({ to, children }: { to: string; children: ReactNode }) {
  const can = useCan();
  return (
    <>
      {children}{' '}
      {can('journal_entries:read') ? (
        <Link to={`/journal/${to}`} className={LINK}>
          {to}
        </Link>
      ) : (
        to
      )}
    </>
  );
}
