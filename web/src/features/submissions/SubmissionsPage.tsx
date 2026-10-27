import { useQueryClient } from '@tanstack/react-query';
import type { ReactElement } from 'react';
import { useNavigate, useParams } from 'react-router';
import { CreateButton } from '@/components/CreateButton';
import { Pager } from '@/components/Pager';
import { QueryState } from '@/components/QueryState';
import { TableSkeleton } from '@/components/Skeletons';
import { SubmissionStatus, TestBadge } from '@/components/StatusBadge';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useForms } from '@/lib/api/queries';
import type { SubmissionSummary } from '@/lib/api/types';
import { money, when } from '@/lib/format';
import type { FromList } from '@/lib/useNeighbours';
import { usePages } from '@/lib/usePages';
import { cn } from '@/lib/utils';
import { submissionQueries, useSubmissions } from './api';

// A row peeks after the pointer rests on it, not as it passes, and starts loading the record so a click is quick
function Peek({ row, tracked, children }: { row: SubmissionSummary; tracked: boolean; children: ReactElement }) {
  const queryClient = useQueryClient();
  return (
    <HoverCard
      openDelay={400}
      onOpenChange={(open) => {
        if (open) queryClient.query(submissionQueries.one(row.form, row.id)).catch(() => undefined);
      }}
    >
      <HoverCardTrigger asChild>{children}</HoverCardTrigger>
      <HoverCardContent align="start" className="w-80 text-sm">
        <div className="flex items-center gap-2">
          <span className="font-medium">{row.title ?? 'No answers'}</span>
          <SubmissionStatus status={row.status} tracked={tracked} />
        </div>
        <div className="mt-1 text-muted-foreground">
          {row.response_number !== null && `#${row.response_number} · `}
          {row.submitted_by ?? '—'}
        </div>
        {row.amount !== null && <div className="mt-2 text-base font-medium">{money(row.amount)}</div>}
        {row.live_entry && (
          <div className="mt-1 font-mono text-xs text-muted-foreground">Live in Mifos: {row.live_entry}</div>
        )}
      </HoverCardContent>
    </HoverCard>
  );
}

// A form's submissions, the newest we received first. A row opens its own page
export function SubmissionsPage() {
  const { form = '' } = useParams();
  const { cursor, search } = usePages();
  const navigate = useNavigate();
  const { data: forms } = useForms();
  const { data, error, isFetching, isPlaceholderData } = useSubmissions(form, cursor);
  const spec = forms?.find((f) => f.key === form);
  const amounts = form === 'requisition';
  const tracked = spec?.tracks_status ?? false;
  const open = (id: string) => void navigate(`/forms/${form}/${id}`, { state: { from: search } satisfies FromList });

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold">{spec?.title ?? ''}</h1>
        <div className="ml-auto">
          <CreateButton noun={(spec?.title ?? 'one').toLowerCase().replace(/s$/, '')} />
        </div>
      </div>
      {!data ? (
        <QueryState error={error} loading={<TableSkeleton columns={amounts ? 5 : 4} />} />
      ) : (
        <>
          <div className={cn('rounded-md border', isPlaceholderData && 'opacity-60')}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="hidden sm:table-cell">#</TableHead>
                  <TableHead>Subject</TableHead>
                  {amounts && <TableHead className="text-right">Amount</TableHead>}
                  <TableHead className="hidden md:table-cell">Submitted by</TableHead>
                  <TableHead className="hidden sm:table-cell">Submitted</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((s) => (
                  <Peek key={s.id} row={s} tracked={tracked}>
                    <TableRow
                      className="cursor-pointer"
                      tabIndex={0}
                      onClick={() => {
                        open(s.id);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') open(s.id);
                      }}
                    >
                      <TableCell className="hidden text-muted-foreground sm:table-cell">
                        {s.response_number ?? '—'}
                      </TableCell>
                      <TableCell className="max-w-40 truncate sm:max-w-64">
                        <span className="mr-2">{s.title ?? <em className="text-muted-foreground">No answers</em>}</span>
                        {s.test && <TestBadge />}
                      </TableCell>
                      {amounts && <TableCell className="text-right">{money(s.amount)}</TableCell>}
                      <TableCell className="hidden md:table-cell">{s.submitted_by ?? '—'}</TableCell>
                      <TableCell className="hidden sm:table-cell">{when(s.submitted_at)}</TableCell>
                      <TableCell>
                        <SubmissionStatus status={s.status} tracked={tracked} />
                      </TableCell>
                    </TableRow>
                  </Peek>
                ))}
                {!data.items.length && (
                  <TableRow>
                    <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                      Nothing yet
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
