import { useQueryClient } from '@tanstack/react-query';
import type { ReactElement } from 'react';
import { FilePen } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router';
import { CreateButton } from '@/components/CreateButton';
import { Pager } from '@/components/Pager';
import { QueryState } from '@/components/QueryState';
import { TableSkeleton } from '@/components/Skeletons';
import { SubmissionStatus, TestBadge } from '@/components/StatusBadge';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { Person } from '@/components/Person';
import { Time } from '@/components/Time';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useDrafts } from '@/features/forms/api';
import { useCan, useForms, useName } from '@/lib/api/queries';
import type { SubmissionSummary } from '@/lib/api/types';
import { money } from '@/lib/format';
import { LINK } from '@/lib/styles';
import type { FromList } from '@/lib/useNeighbours';
import { usePages } from '@/lib/usePages';
import { cn } from '@/lib/utils';
import { submissionQueries, useSubmissions, useTests } from './api';

// Yours alone, unsubmitted, above the list: a draft is in no list until it's submitted
function YourDrafts({ form }: { form: string }) {
  const can = useCan();
  const { data: drafts = [] } = useDrafts(form, can(`forms:${form}:submit`));
  if (!drafts.length) return null;
  return (
    // Amber: not wrong, but waiting on you, to submit or discard
    <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-950/40">
      <h2 className="mb-2 font-medium text-amber-900 dark:text-amber-200">Your drafts</h2>
      <ul className="space-y-1">
        {drafts.map((d) => (
          <li key={d.id} className="flex items-center gap-2">
            <FilePen className="size-4 shrink-0 text-amber-700 dark:text-amber-300" />
            <Link to={`/forms/${form}/${d.id}`} className={`truncate ${LINK}`}>
              {d.title ?? 'Untitled'}
            </Link>
            <span className="ml-auto shrink-0 text-muted-foreground">
              <Time at={d.updated_at} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

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
          {row.submitted_by ? <NameOf email={row.submitted_by} /> : '—'}
        </div>
        {row.amount !== null && <div className="mt-2 text-base font-medium">{money(row.amount)}</div>}
        {row.live_entry && <div className="mt-1 text-xs text-muted-foreground">Live in Mifos: {row.live_entry}</div>}
      </HoverCardContent>
    </HoverCard>
  );
}

// A form's submissions, the newest we received first. A row opens its own page
export function SubmissionsPage() {
  const { form = '' } = useParams();
  const { cursor, search } = usePages();
  const tests = useTests(form);
  const navigate = useNavigate();
  const { data: forms } = useForms();
  const { data, error, isFetching, isPlaceholderData } = useSubmissions(form, cursor, tests);
  const spec = forms?.find((f) => f.key === form);
  const amounts = form === 'requisition';
  const tracked = spec?.tracks_status ?? false;
  const open = (id: string) => void navigate(`/forms/${form}/${id}`, { state: { from: search } satisfies FromList });

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold">{spec?.title ?? ''}</h1>
        <div className="ml-auto">
          <CreateButton form={form} noun={(spec?.title ?? 'one').toLowerCase().replace(/s$/, '')} />
        </div>
      </div>
      <YourDrafts form={form} />
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
                      <TableCell className="hidden md:table-cell">
                        <Person email={s.submitted_by} />
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        <Time at={s.submitted_at} />
                      </TableCell>
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

// Just the name, in a card that's itself a hover: a card in a card would close the first
function NameOf({ email }: { email: string }) {
  return <>{useName(email)}</>;
}
