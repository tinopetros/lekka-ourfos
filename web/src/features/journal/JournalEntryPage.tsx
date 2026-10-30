import { Link, useParams } from 'react-router';
import { Field } from '@/components/Field';
import { EntrySummary } from '@/components/EntrySummary';
import { QueryState } from '@/components/QueryState';
import { Time } from '@/components/Time';
import { RecordHeader } from '@/components/RecordHeader';
import { RecordTab, RecordTabs } from '@/components/RecordTabs';
import { RecordSkeleton } from '@/components/Skeletons';
import { Person } from '@/components/Person';
import { Tabs, TabsContent } from '@/components/ui/tabs';
import { useForms } from '@/lib/api/queries';
import type { Submission } from '@/lib/api/types';
import { day } from '@/lib/format';
import { LINK } from '@/lib/styles';
import { useNeighbours } from '@/lib/useNeighbours';
import { useTab } from '@/lib/useTab';
import { useSubmission } from '@/features/submissions/api';
import { journalQueries, useJournalEntry } from './api';

function Entry({ id }: { id: string }) {
  return (
    <Link to={`/journal/${id}`} className={LINK}>
      {id}
    </Link>
  );
}

// What posted it, by its form's name, as #482: its subject
function Posted({ form, id, s }: { form: string; id: string; s: Submission | undefined }) {
  const { data: forms } = useForms();
  const title = forms?.find((f) => f.key === form)?.title ?? 'Submission';
  const label = s ? `${s.response_number !== null ? `#${s.response_number}: ` : ''}${s.title ?? id}` : id;
  return (
    <Field label={title.replace(/s$/, '')}>
      <Link to={`/forms/${form}/${id}`} className={LINK}>
        {label}
      </Link>
    </Field>
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
  const [tab, setTab] = useTab(['lines', 'details']);
  // Whatever posted it, fetched with the entry: its submitter heads the page, and Details links it by name
  const { data: s } = useSubmission(e?.form ?? '', e?.submission ?? '', undefined, Boolean(e?.form && e.submission));

  return (
    <div className="mx-auto max-w-5xl">
      <RecordHeader
        list="Journal entries"
        listPath="/journal"
        from={neighbours.from}
        current={`Transaction ID: ${id}`}
        noun="journal entry"
        neighbours={neighbours}
      />
      {!e ? (
        <QueryState error={error} loading={<RecordSkeleton />} />
      ) : (
        <>
          <div className="mb-2 flex flex-wrap items-center gap-3">
            <h1 className="text-lg font-semibold">Transaction ID: {id}</h1>
          </div>
          <p className="mb-8 text-sm text-muted-foreground">
            {s ? (
              <>
                Submitted by <Person email={s.submitted_by} /> on <Time at={s.submitted_at ?? s.received_at} />
              </>
            ) : (
              <>
                Posted by {e.by ?? '—'} on {day(e.created_on)}
              </>
            )}
          </p>
          {e.reversing && !e.reversed_by && (
            <p role="alert" className="mb-6 rounded-md border border-amber-500 bg-amber-50 p-3 text-sm text-amber-900">
              Correction run {e.reversing} posted this entry&apos;s mirror without hearing back. Check Mifos before
              correcting it again.
            </p>
          )}
          <Tabs value={tab} onValueChange={setTab}>
            <RecordTabs>
              <RecordTab value="lines">Journal entry</RecordTab>
              <RecordTab value="details">Details</RecordTab>
            </RecordTabs>
            <TabsContent value="lines" className="pt-6">
              <EntrySummary e={e} live={e.status === 'live'} />
            </TabsContent>
            <TabsContent value="details" className="pt-6">
              <dl className="divide-y">
                {e.form && e.submission && <Posted form={e.form} id={e.submission} s={s} />}
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
                <Field label="Recorded by">{e.by ?? '—'}</Field>
                <Field label="Source">{e.source ?? '—'}</Field>
                <Field label="Posted on">{day(e.created_on)}</Field>
                <Field label="Recorded">
                  <Time at={e.recorded_at} />
                </Field>
                {e.run && <Field label="Workflow run">{e.run}</Field>}
              </dl>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
