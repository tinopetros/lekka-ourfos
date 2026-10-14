import { Outlet, useNavigate, useParams } from 'react-router';
import { Pager } from '@/components/Pager';
import { QueryState } from '@/components/QueryState';
import { StatusBadge, TestBadge } from '@/components/StatusBadge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useForms, useSubmissions } from '@/lib/api/queries';
import { money, when } from '@/lib/format';
import { usePages } from '@/lib/usePages';
import { cn } from '@/lib/utils';

/** A form's submissions, the newest we received first. A row opens its sheet. */
export function SubmissionsPage() {
  const { form = '', id } = useParams();
  const { cursor, search } = usePages();
  const navigate = useNavigate();
  const { data: forms } = useForms();
  const { data, error, isFetching, isPlaceholderData } = useSubmissions(form, cursor);
  const title = forms?.find((f) => f.key === form)?.title ?? '';
  const amounts = form === 'requisition';

  return (
    <div className="space-y-3">
      <h1 className="text-lg font-semibold">{title}</h1>
      {!data ? (
        <QueryState error={error} />
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
                  <TableHead className="hidden lg:table-cell">Submitted</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="hidden sm:table-cell">Received</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((s) => (
                  <TableRow
                    key={s.id}
                    data-state={s.id === id ? 'selected' : undefined}
                    className="cursor-pointer"
                    tabIndex={0}
                    onClick={() => void navigate({ pathname: `/forms/${form}/${s.id}`, search })}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') void navigate({ pathname: `/forms/${form}/${s.id}`, search });
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
                    <TableCell className="hidden lg:table-cell">{when(s.submitted_at)}</TableCell>
                    <TableCell>
                      <StatusBadge status={s.status} />
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">{when(s.received_at)}</TableCell>
                  </TableRow>
                ))}
                {!data.items.length && (
                  <TableRow>
                    <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
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
      <Outlet context={data?.items} />
    </div>
  );
}
