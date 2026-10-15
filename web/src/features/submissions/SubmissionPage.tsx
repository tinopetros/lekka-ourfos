import { Link, useParams } from 'react-router';
import { Field, Section } from '@/components/Field';
import { FileDialog } from '@/components/FileDialog';
import { Lines } from '@/components/Lines';
import { QueryState } from '@/components/QueryState';
import { RecordHeader } from '@/components/RecordHeader';
import { RecordSkeleton } from '@/components/Skeletons';
import { StatusBadge, TestBadge } from '@/components/StatusBadge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useForms } from '@/lib/api/queries';
import type { Answer, Run, Submission } from '@/lib/api/types';
import { money, when } from '@/lib/format';
import { useNeighbours } from '@/lib/useNeighbours';
import { submissionQueries, useSubmission } from './api';

function AnswerValue({ answer }: { answer: Answer }) {
  if (answer.link)
    return (
      <a href={answer.link} target="_blank" rel="noreferrer" className="underline underline-offset-2">
        {answer.link}
      </a>
    );
  if (answer.files.length)
    return (
      <span className="flex flex-wrap gap-3">
        {answer.files.map((f) => (
          <FileDialog key={f.name} file={f} />
        ))}
      </span>
    );
  return <>{answer.text}</>;
}

function EntryLink({ id }: { id: string }) {
  return (
    <Link to={`/journal/${id}`} className="font-mono text-xs underline underline-offset-2">
      {id}
    </Link>
  );
}

// Where it stands: its answers, then the entry live in Mifos
function Overview({ s }: { s: Submission }) {
  const live = s.journal_entries.find((e) => e.transaction_id === s.live_entry);
  return (
    <div className="space-y-6">
      <Section title="Answers">
        {s.answers.length ? (
          <dl className="divide-y">
            {s.answers.map((a) => (
              <Field key={a.label} label={a.label}>
                <AnswerValue answer={a} />
              </Field>
            ))}
          </dl>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">Its answers never validated. What was sent:</p>
            <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(s.raw, null, 2)}</pre>
          </>
        )}
      </Section>
      {live && (
        <Section title="Live in Mifos">
          <p className="text-sm">
            <EntryLink id={live.transaction_id} />
          </p>
          <Lines lines={live.lines} currency={live.currency} />
        </Section>
      )}
    </div>
  );
}

const TITLES: Record<Run['workflow'], string> = {
  expense: 'Received',
  intake: 'Received',
  correction: 'Corrected',
  unknown: 'Run',
};

// One run on the timeline: what happened, why, and the lines it posted, inline
function Event({ run }: { run: Run }) {
  return (
    <li className="relative pb-6 pl-6 last:pb-0">
      <span className="absolute top-1.5 -left-[5px] size-2.5 rounded-full border-2 border-foreground/40 bg-background" />
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">
          {run.workflow === 'unknown' ? (run.name ?? TITLES.unknown) : TITLES[run.workflow]}
          {run.workflow === 'correction' && run.request?.requested_by && ` by ${run.request.requested_by}`}
        </span>
        <StatusBadge status={run.status} />
        {run.test && <TestBadge />}
        <span className="ml-auto text-xs text-muted-foreground">{when(run.started_at)}</span>
      </div>
      <div className="mt-1 space-y-1 text-sm text-muted-foreground">
        {run.reason && <p>{run.reason}</p>}
        {run.workflow === 'expense' && run.classification && (
          <p>
            Expenser {run.classification.approve ? 'approved' : 'rejected'} it
            {run.classification.reason ? `: ${run.classification.reason}` : ''}
          </p>
        )}
        {run.workflow === 'expense' && run.skipped && <p>Not posted: posting was off</p>}
        {run.workflow === 'correction' && (
          <>
            {run.request?.reason && <p>&ldquo;{run.request.reason}&rdquo;</p>}
            {run.entry && (
              <p>
                Reversed <EntryLink id={run.entry} />
                {run.reversal && (
                  <>
                    {' '}
                    with its mirror <EntryLink id={run.reversal} />
                  </>
                )}
              </p>
            )}
          </>
        )}
        {(run.workflow === 'expense' || run.workflow === 'correction') && run.mifos_transaction_id && (
          <p>
            {run.workflow === 'correction' ? 'Posted instead' : 'Posted'} <EntryLink id={run.mifos_transaction_id} />
          </p>
        )}
        {run.emails.length > 0 && (
          <p className="text-xs">Emails: {run.emails.map((e) => e.kind.replaceAll('_', ' ')).join(', ')}</p>
        )}
      </div>
      {(run.workflow === 'expense' || run.workflow === 'correction') && run.posted.length > 0 && (
        <div className="mt-2">
          <Lines lines={run.posted} />
        </div>
      )}
    </li>
  );
}

// Its runs, oldest first, as a story
function History({ s }: { s: Submission }) {
  const runs = [...s.runs].reverse();
  return (
    <ol className="ml-1.5 border-l pl-0">
      {runs.map((r) => (
        <Event key={r.id} run={r} />
      ))}
    </ol>
  );
}

// A submission on its own page: where it stands, and its history
export function SubmissionPage() {
  const { form = '', id = '' } = useParams();
  const { data: forms } = useForms();
  const neighbours = useNeighbours({
    id,
    list: (cursor) => submissionQueries.list(form, cursor),
    idOf: (row) => row.id,
    pathOf: (row) => `/forms/${form}/${row.id}`,
  });
  const { data: s, error, isPlaceholderData } = useSubmission(form, id);
  const list = forms?.find((f) => f.key === form)?.title ?? 'Back';
  const current = s ? `${s.response_number !== null ? `#${s.response_number} ` : ''}${s.title ?? id}` : id;

  return (
    <div className="mx-auto max-w-5xl">
      <RecordHeader
        list={list}
        listPath={`/forms/${form}`}
        from={neighbours.from}
        current={current}
        noun="submission"
        neighbours={neighbours}
      />
      {!s || isPlaceholderData ? (
        <QueryState error={error} loading={<RecordSkeleton />} />
      ) : (
        <>
          <div className="mb-1 flex flex-wrap items-center gap-3">
            <h1 className="text-lg font-semibold">{s.title ?? id}</h1>
            <StatusBadge status={s.status} />
            {s.test && <TestBadge />}
            {s.amount !== null && <span className="ml-auto text-lg font-semibold">{money(s.amount)}</span>}
          </div>
          <p className="mb-4 text-sm text-muted-foreground">
            {s.response_number !== null && `#${s.response_number} · `}
            {s.submitted_by ?? '—'} · {when(s.submitted_at ?? s.received_at)}
          </p>
          <Tabs defaultValue="overview">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="history">History ({s.runs.length})</TabsTrigger>
            </TabsList>
            <TabsContent value="overview" className="pt-4">
              <Overview s={s} />
            </TabsContent>
            <TabsContent value="history" className="pt-4">
              <History s={s} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
