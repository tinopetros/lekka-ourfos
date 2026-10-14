import { Outlet, useNavigate, useParams } from 'react-router';
import { Pager } from '@/components/Pager';
import { QueryState } from '@/components/QueryState';
import { StatusBadge } from '@/components/StatusBadge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useJournalEntries } from './api';
import type { JournalEntry } from '@/lib/api/types';
import { day, money, when } from '@/lib/format';
import { usePages } from '@/lib/usePages';
import { cn } from '@/lib/utils';

const total = (e: JournalEntry) => e.lines.filter((l) => l.type === 'DEBIT').reduce((sum, l) => sum + l.amount, 0);

/** The journal entries we posted to Mifos, latest first. Mifos itself is never read (phase 12 ADR 11). */
export function JournalPage() {
  const { id } = useParams();
  const { cursor, search } = usePages();
  const navigate = useNavigate();
  const { data, error, isFetching, isPlaceholderData } = useJournalEntries(cursor);

  return (
    <div className="space-y-3">
      <h1 className="text-lg font-semibold">Journal entries</h1>
      {!data ? (
        <QueryState error={error} />
      ) : (
        <>
          <div className={cn('rounded-md border', isPlaceholderData && 'opacity-60')}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Transaction</TableHead>
                  <TableHead className="hidden sm:table-cell">Date</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="hidden md:table-cell">By</TableHead>
                  <TableHead className="hidden lg:table-cell">Recorded</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((e) => (
                  <TableRow
                    key={e.transaction_id}
                    data-state={e.transaction_id === id ? 'selected' : undefined}
                    className="cursor-pointer"
                    tabIndex={0}
                    onClick={() => void navigate({ pathname: `/journal/${e.transaction_id}`, search })}
                    onKeyDown={(k) => {
                      if (k.key === 'Enter') void navigate({ pathname: `/journal/${e.transaction_id}`, search });
                    }}
                  >
                    <TableCell className="max-w-36 truncate font-mono text-xs sm:max-w-none">
                      {e.transaction_id}
                      {e.reverses && <span className="ml-2 font-sans text-muted-foreground">mirror</span>}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">{day(e.transaction_date)}</TableCell>
                    <TableCell className="text-right">{money(total(e), e.currency ?? 'USD')}</TableCell>
                    <TableCell>
                      <StatusBadge status={e.status} />
                    </TableCell>
                    <TableCell className="hidden md:table-cell">{e.by ?? '—'}</TableCell>
                    <TableCell className="hidden lg:table-cell">{when(e.recorded_at)}</TableCell>
                  </TableRow>
                ))}
                {!data.items.length && (
                  <TableRow>
                    <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                      Nothing posted yet
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
          <Pager next={data.next} fetching={isFetching} />
        </>
      )}
      <Outlet />
    </div>
  );
}
