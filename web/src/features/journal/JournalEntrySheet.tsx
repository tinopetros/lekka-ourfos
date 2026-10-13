import { Link, useNavigate, useParams } from 'react-router';
import { Field, Section } from '@/components/Field';
import { Lines } from '@/components/Lines';
import { QueryState } from '@/components/QueryState';
import { StatusBadge } from '@/components/StatusBadge';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useJournalEntry } from '@/lib/api/queries';
import { day, when } from '@/lib/format';
import { usePages } from '@/lib/usePages';

function Entry({ id }: { id: string }) {
  return (
    <Link to={`/journal/${id}`} className="underline underline-offset-2">
      {id}
    </Link>
  );
}

export function JournalEntrySheet() {
  const { id = '' } = useParams();
  const { search } = usePages();
  const navigate = useNavigate();
  const { data: e, error } = useJournalEntry(id);

  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) void navigate({ pathname: '/journal', search });
      }}
    >
      <SheetContent className="w-full overflow-y-auto data-[side=right]:sm:max-w-xl">
        <SheetHeader>
          <SheetTitle className="font-mono">{id}</SheetTitle>
          <SheetDescription>{e && `${day(e.transaction_date)} · ${e.currency ?? ''}`}</SheetDescription>
        </SheetHeader>
        {!e ? (
          <QueryState error={error} />
        ) : (
          <div className="space-y-6 px-4 pb-6">
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
              <Field label="Status">
                <StatusBadge status={e.status} />
              </Field>
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
              <Field label="Recorded">{when(e.recorded_at)}</Field>
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
      </SheetContent>
    </Sheet>
  );
}
