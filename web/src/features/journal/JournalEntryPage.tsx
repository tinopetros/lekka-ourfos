import { Link, useParams } from 'react-router';
import { Field, Section } from '@/components/Field';
import { Lines } from '@/components/Lines';
import { QueryState } from '@/components/QueryState';
import { Time } from '@/components/Time';
import { RecordHeader } from '@/components/RecordHeader';
import { RecordSkeleton } from '@/components/Skeletons';
import { StatusBadge } from '@/components/StatusBadge';
import { day } from '@/lib/format';
import { useNeighbours } from '@/lib/useNeighbours';
import { journalQueries, useJournalEntry } from './api';

function Entry({ id }: { id: string }) {
  return (
    <Link to={`/journal/${id}`} className="font-mono text-xs underline underline-offset-2">
      {id}
    </Link>
  );
}

export function JournalEntryPage() {
  const { id = '' } = useParams();
  const neighbours = useNeighbours({
    id,
    list: journalQueries.list,
    idOf: (e) => e.transaction_id,
    pathOf: (e) => `/journal/${e.transaction_id}`,
  });
  const { data: e, error } = useJournalEntry(id);

  return (
    <div className="mx-auto max-w-5xl">
      <RecordHeader
        list="Journal entries"
        listPath="/journal"
        from={neighbours.from}
        current={id}
        noun="journal entry"
        neighbours={neighbours}
      />
      {!e ? (
        <QueryState error={error} loading={<RecordSkeleton />} />
      ) : (
        <div className="space-y-6">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-mono text-lg font-semibold">{id}</h1>
              <StatusBadge status={e.status} />
            </div>
            <p className="text-sm text-muted-foreground">
              {day(e.transaction_date)} · {e.currency ?? ''}
            </p>
          </div>
          {e.reversing && !e.reversed_by && (
            <p role="alert" className="rounded-md border border-amber-500 bg-amber-50 p-3 text-sm text-amber-900">
              Correction run {e.reversing} posted this entry&apos;s mirror without hearing back. Check Mifos before
              correcting it again.
            </p>
          )}
          <Section title="Lines">
            <Lines lines={e.lines} currency={e.currency} />
          </Section>
          <dl className="divide-y">
            {e.reverses && (
              <Field label="Reverses">
                <Entry id={e.reverses} />
              </Field>
            )}
            {e.reversed_by && (
              <Field label="Reversed by">
                <Entry id={e.reversed_by} />
              </Field>
            )}
            <Field label="Reference number">{e.reference_number ?? '—'}</Field>
            <Field label="Comments">{e.comments ?? '—'}</Field>
            <Field label="By">{e.by ?? '—'}</Field>
            <Field label="Source">{e.source ?? '—'}</Field>
            <Field label="Posted on">{day(e.created_on)}</Field>
            <Field label="Recorded">
              <Time at={e.recorded_at} />
            </Field>
            {e.form && e.submission && (
              <Field label="Submission">
                <Link to={`/forms/${e.form}/${e.submission}`} className="underline underline-offset-2">
                  {e.submission}
                </Link>
              </Field>
            )}
            {e.run && <Field label="Workflow run">{e.run}</Field>}
          </dl>
        </div>
      )}
    </div>
  );
}
