import { ExternalLink } from 'lucide-react';
import { Link, useNavigate, useOutletContext, useParams } from 'react-router';
import { Field, Section } from '@/components/Field';
import { Lines } from '@/components/Lines';
import { QueryState } from '@/components/QueryState';
import { StatusBadge, TestBadge } from '@/components/StatusBadge';
import { Separator } from '@/components/ui/separator';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useSubmission } from '@/lib/api/queries';
import type { Answer, CorrectionRun, ExpenseRun, Run, SubmissionSummary } from '@/lib/api/types';
import { when } from '@/lib/format';
import { usePages } from '@/lib/usePages';

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
        {answer.files.map((f) =>
          f.url ? (
            <a
              key={f.name}
              href={f.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 underline"
            >
              {f.name} <ExternalLink className="size-3" />
            </a>
          ) : (
            <span key={f.name}>{f.name}</span>
          ),
        )}
      </span>
    );
  return <>{answer.text}</>;
}

function EntryLink({ id }: { id: string }) {
  return (
    <Link to={`/journal/${id}`} className="underline underline-offset-2">
      {id}
    </Link>
  );
}

/** What an expense run adds: expenser's call, and what was posted. */
function ExpenseFields({ run }: { run: ExpenseRun }) {
  const c = run.classification;
  return (
    <>
      {c && (
        <Field label="Expenser">
          {c.approve === null ? '' : c.approve ? 'Approved' : 'Rejected'}
          {c.reason ? `: ${c.reason}` : ''}
          {c.comments.length > 0 && (
            <ul className="mt-1 list-disc pl-4 text-muted-foreground">
              {c.comments.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          )}
        </Field>
      )}
      {run.skipped && <Field label="Posting">Skipped: {run.skipped === 'mifos' ? 'posting off' : run.skipped}</Field>}
      {run.mifos_transaction_id && (
        <Field label="Mifos transaction">
          <EntryLink id={run.mifos_transaction_id} />
        </Field>
      )}
    </>
  );
}

/** What a correction adds: who asked and why, the entry it reversed, its mirror, and what replaced it. */
function CorrectionFields({ run }: { run: CorrectionRun }) {
  return (
    <>
      {run.request && (
        <>
          <Field label="Requested by">{run.request.requested_by}</Field>
          <Field label="Reason">{run.request.reason}</Field>
        </>
      )}
      {run.entry && (
        <Field label="Corrects">
          <EntryLink id={run.entry} />
        </Field>
      )}
      {run.reversal && (
        <Field label="Its mirror">
          <EntryLink id={run.reversal} />
        </Field>
      )}
      {run.mifos_transaction_id && (
        <Field label="Posted instead">
          <EntryLink id={run.mifos_transaction_id} />
        </Field>
      )}
    </>
  );
}

/** One run: what every run has, then what its workflow adds. */
function RunCard({ run }: { run: Run }) {
  const title = run.workflow === 'unknown' ? (run.name ?? 'Run') : run.workflow;
  const posted = run.workflow === 'expense' || run.workflow === 'correction' ? run.posted : [];
  return (
    <div className="space-y-2 rounded-md border p-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium capitalize">{title}</span>
        <StatusBadge status={run.status} />
        {run.test && <TestBadge />}
        <span className="ml-auto text-xs text-muted-foreground">{when(run.started_at)}</span>
      </div>
      <dl className="divide-y">
        {run.reason && <Field label="Why">{run.reason}</Field>}
        {run.workflow === 'expense' && <ExpenseFields run={run} />}
        {run.workflow === 'correction' && <CorrectionFields run={run} />}
        {run.emails.length > 0 && (
          <Field label="Emails">
            {run.emails.map((e) => `${e.kind.replaceAll('_', ' ')} ${when(e.at)}`).join('\n')}
          </Field>
        )}
      </dl>
      {posted.length > 0 && <Lines lines={posted} />}
    </div>
  );
}

/** What a row opens: its answers, every run on it, and the entries it posted. Read only. */
export function SubmissionSheet() {
  const { form = '', id = '' } = useParams();
  const { search } = usePages();
  const navigate = useNavigate();
  const rows = useOutletContext<SubmissionSummary[] | undefined>();
  const { data, error, isPlaceholderData } = useSubmission(
    form,
    id,
    rows?.find((r) => r.id === id),
  );

  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) void navigate({ pathname: `/forms/${form}`, search });
      }}
    >
      <SheetContent className="w-full overflow-y-auto data-[side=right]:sm:max-w-xl">
        <SheetHeader>
          <SheetTitle className="flex flex-wrap items-center gap-2 pr-8">
            {data?.title ?? id} {data?.test && <TestBadge />}
          </SheetTitle>
          <SheetDescription>
            {data?.response_number !== null && data?.response_number !== undefined && `#${data.response_number} · `}
            {data?.submitted_by ?? ''} {data?.submitted_at && `· ${when(data.submitted_at)}`}
          </SheetDescription>
        </SheetHeader>
        {!data ? (
          <QueryState error={error} />
        ) : (
          <div className="space-y-6 px-4 pb-6">
            <div className="flex items-center gap-2 text-sm">
              Status <StatusBadge status={data.status} />
            </div>
            {isPlaceholderData ? (
              <QueryState error={error} />
            ) : (
              <>
                <Section title="Answers">
                  {data.answers.length ? (
                    <dl className="divide-y">
                      {data.answers.map((a) => (
                        <Field key={a.label} label={a.label}>
                          <AnswerValue answer={a} />
                        </Field>
                      ))}
                    </dl>
                  ) : (
                    <>
                      <p className="text-sm text-muted-foreground">Its answers never validated. What was sent:</p>
                      <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">
                        {JSON.stringify(data.raw, null, 2)}
                      </pre>
                    </>
                  )}
                </Section>
                <Separator />
                <Section title={`Runs (${data.runs.length})`}>
                  {data.runs.map((r) => (
                    <RunCard key={r.id} run={r} />
                  ))}
                </Section>
                {data.journal_entries.length > 0 && (
                  <>
                    <Separator />
                    <Section title="Journal entries">
                      <ul className="space-y-1 text-sm">
                        {data.journal_entries.map((e) => (
                          <li key={e.transaction_id} className="flex items-center gap-2">
                            <Link to={`/journal/${e.transaction_id}`} className="underline underline-offset-2">
                              {e.transaction_id}
                            </Link>
                            <StatusBadge status={e.status} />
                            {e.reverses && <span className="text-muted-foreground">reverses {e.reverses}</span>}
                            {e.transaction_id === data.live_entry && (
                              <span className="text-muted-foreground">live</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </Section>
                  </>
                )}
              </>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
