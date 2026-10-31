import { useNavigate } from 'react-router';
import { Lines } from '@/components/Lines';
import { Pager } from '@/components/Pager';
import { Name } from '@/components/Person';
import { QueryState } from '@/components/QueryState';
import { TableSkeleton } from '@/components/Skeletons';
import { Time } from '@/components/Time';
import { StatusBadge, TestBadge } from '@/components/StatusBadge';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { JournalEntry } from '@/lib/api/types';
import { day, money } from '@/lib/format';
import type { FromList } from '@/lib/useNeighbours';
import { usePages } from '@/lib/usePages';
import { cn } from '@/lib/utils';
import { useTests } from '@/features/submissions/api';
import { useJournalEntries } from './api';

const total = (e: JournalEntry) => e.lines.filter((l) => l.type === 'DEBIT').reduce((sum, l) => sum + l.amount, 0);

// The journal entries we posted to Mifos, latest first. Mifos itself is never read
export function JournalPage() {
  const { cursor, search } = usePages();
  // Entries are requisitions': whoever may make test requisitions may see their entries
  const tests = useTests('requisition');
  const navigate = useNavigate();
  const { data, error, isFetching, isPlaceholderData } = useJournalEntries(cursor, tests);
  const open = (id: string) => void navigate(`/journal/${id}`, { state: { from: search } satisfies FromList });

  return (
    <div className="space-y-3">
      <h1 className="text-lg font-semibold">Journal entries</h1>
      {!data ? (
        <QueryState error={error} loading={<TableSkeleton columns={6} />} />
      ) : (
        <>
          <div className={cn('rounded-md border', isPlaceholderData && 'opacity-60')}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Transaction ID</TableHead>
                  <TableHead className="hidden sm:table-cell">Transaction date</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead className="hidden md:table-cell">Recorded by</TableHead>
                  <TableHead className="hidden lg:table-cell">Recorded</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((e) => (
                  // The lines are in the row already: a peek costs nothing
                  <HoverCard key={e.transaction_id} openDelay={400}>
                    <HoverCardTrigger asChild>
                      <TableRow
                        className="cursor-pointer"
                        tabIndex={0}
                        onClick={() => {
                          open(e.transaction_id);
                        }}
                        onKeyDown={(k) => {
                          if (k.key === 'Enter') open(e.transaction_id);
                        }}
                      >
                        <TableCell className="max-w-36 truncate text-xs sm:max-w-none">
                          {e.transaction_id}
                          {e.reverses && <span className="ml-2 text-muted-foreground">mirror</span>}
                          {e.test && (
                            <span className="ml-2">
                              <TestBadge />
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">{day(e.transaction_date)}</TableCell>
                        <TableCell className="text-right">{money(total(e), e.currency ?? 'USD')}</TableCell>
                        <TableCell className="hidden md:table-cell">
                          <Name email={e.by} />
                        </TableCell>
                        <TableCell className="hidden lg:table-cell">
                          <Time at={e.recorded_at} />
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={e.status} />
                        </TableCell>
                      </TableRow>
                    </HoverCardTrigger>
                    <HoverCardContent align="start" className="w-96">
                      <Lines lines={e.lines} currency={e.currency} />
                    </HoverCardContent>
                  </HoverCard>
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
    </div>
  );
}
