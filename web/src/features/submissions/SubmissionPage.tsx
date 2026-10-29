import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { Field, Section } from '@/components/Field';
import { FileLink } from '@/components/FileLink';
import { Lines } from '@/components/Lines';
import { QueryState } from '@/components/QueryState';
import { Person } from '@/components/Person';
import { Time } from '@/components/Time';
import { RecordHeader } from '@/components/RecordHeader';
import { RecordSkeleton } from '@/components/Skeletons';
import { StatusBadge, SubmissionStatus, TestBadge } from '@/components/StatusBadge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useCan, useForms } from '@/lib/api/queries';
import type { Answer, Run, Submission } from '@/lib/api/types';
import { money } from '@/lib/format';
import { useNeighbours } from '@/lib/useNeighbours';
import { SubmissionForm } from '@/features/forms/SubmissionForm';
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
          <FileLink key={f.ref ?? f.drive_id ?? f.name} file={f} />
        ))}
      </span>
    );
  return <>{answer.text}</>;
}

// A link to the entry's own page, for whoever may read the journal. Its lines show here either way
function EntryLink({ id }: { id: string }) {
  const can = useCan();
  if (!can('journal_entries:read')) return <span className="font-mono text-xs">{id}</span>;
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
            {/* Who and when first, as its email has them */}
            <Field label="Submitted by">
              <Person email={s.submitted_by} />
            </Field>
            <Field label="Submitted at">
              <Time at={s.submitted_at ?? s.received_at} />
            </Field>
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

// Boxed when open, its bottom edge the page's colour, so it joins what's below. Important, to win over the line
// variant's dark mode; its underline off
const TAB =
  '-mb-px h-auto flex-none rounded-b-none rounded-t-md border px-4 py-1.5 after:hidden data-active:border-border! data-active:border-b-background! data-active:text-foreground focus-visible:ring-0 focus-visible:outline-none';

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
          {run.workflow === 'correction' && run.request?.requested_by && (
            <>
              {' '}
              by <Person email={run.request.requested_by} />
            </>
          )}
        </span>
        <StatusBadge status={run.status} />
        {run.test && <TestBadge />}
        <span className="ml-auto text-xs text-muted-foreground">
          <Time at={run.started_at} />
        </span>
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

/** A submission on its own page. Its form while it's new or a draft, the same page throughout: what's typed stays
 * where it is when the URL becomes the draft's */
export function SubmissionPage() {
  const { form = '', id = '' } = useParams();
  // A new one's id, made here: while this page is open, its URL becoming the draft's keeps it the same form. Opened
  // again, or reloaded, a draft comes from the API
  const [minted] = useState(() => crypto.randomUUID());
  // Submitted, it's the record
  const [submitted, setSubmitted] = useState(false);
  if (!submitted && (id === 'new' || id === minted))
    return (
      <SubmissionForm
        key={minted}
        form={form}
        id={minted}
        onSubmitted={() => {
          setSubmitted(true);
        }}
      />
    );
  return <Record form={form} id={id} />;
}

// Where it stands, and its history. A draft opened again is its form
function Record({ form, id }: { form: string; id: string }) {
  const { data: forms } = useForms();
  const neighbours = useNeighbours({
    id,
    list: (cursor) => submissionQueries.list(form, cursor),
    idOf: (row) => row.id,
    pathOf: (row) => `/forms/${form}/${row.id}`,
  });
  const { data: s, error, isPlaceholderData } = useSubmission(form, id);
  const spec = forms?.find((f) => f.key === form);
  const list = spec?.title ?? 'Back';
  // #482: its subject, in the breadcrumb and as the title
  const current = s ? `${s.response_number !== null ? `#${s.response_number}: ` : ''}${s.title ?? id}` : id;
  if (s?.status === 'draft' && !isPlaceholderData)
    return <SubmissionForm key={id} form={form} id={id} draft={s.draft} draftTest={s.test} />;

  return (
    <div className="mx-auto max-w-5xl">
      <RecordHeader
        list={list}
        listPath={`/forms/${form}`}
        from={neighbours.from}
        current={current}
        noun={spec ? spec.title.toLowerCase().replace(/s$/, '') : 'submission'}
        neighbours={neighbours}
      />
      {!s || isPlaceholderData ? (
        <QueryState error={error} loading={<RecordSkeleton />} />
      ) : (
        <>
          <div className="mb-2 flex flex-wrap items-center gap-3">
            <h1 className="text-lg font-semibold">{current}</h1>
            <SubmissionStatus status={s.status} tracked={spec?.tracks_status ?? false} />
            {s.test && <TestBadge />}
            {s.amount !== null && <span className="ml-auto text-lg font-semibold">{money(s.amount)}</span>}
          </div>
          <p className="mb-8 text-sm text-muted-foreground">
            Submitted
            {s.submitted_by && (
              <>
                {' '}
                by <Person email={s.submitted_by} />
              </>
            )}{' '}
            at <Time at={s.submitted_at ?? s.received_at} />
          </p>
          {/* A line across the page, the open tab a box sitting on it, open at the bottom: everything below is that tab's */}
          <Tabs defaultValue="overview">
            <div className="border-b">
              <TabsList variant="line" className="gap-0 p-0 group-data-horizontal/tabs:h-auto">
                <TabsTrigger value="overview" className={TAB}>
                  Overview
                </TabsTrigger>
                <TabsTrigger value="history" className={TAB}>
                  History ({s.runs.length})
                </TabsTrigger>
              </TabsList>
            </div>
            <TabsContent value="overview" className="pt-6">
              <Overview s={s} />
            </TabsContent>
            <TabsContent value="history" className="pt-6">
              <History s={s} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
