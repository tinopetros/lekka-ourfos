import { ArrowRight } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { Field, Section } from '@/components/Field';
import { EntrySummary } from '@/components/EntrySummary';
import { FileLink } from '@/components/FileLink';
import { Lines } from '@/components/Lines';
import { QueryState } from '@/components/QueryState';
import { Person } from '@/components/Person';
import { Time } from '@/components/Time';
import { RecordHeader } from '@/components/RecordHeader';
import { RecordTab, RecordTabs } from '@/components/RecordTabs';
import { RecordSkeleton } from '@/components/Skeletons';
import { StatusBadge, SubmissionStatus, TestBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent } from '@/components/ui/tabs';
import { useCan, useForms } from '@/lib/api/queries';
import type { Action, ActionKind, Answer, JournalEntry, Run, Submission } from '@/lib/api/types';
import { money } from '@/lib/format';
import { LINK } from '@/lib/styles';
import { useNeighbours } from '@/lib/useNeighbours';
import { useTab } from '@/lib/useTab';
import { SubmissionForm } from '@/features/forms/SubmissionForm';
import { submissionQueries, useCorrection, useSubmission, useTests } from './api';
import { useFlag } from '@/lib/flags';
import { useAction } from './actions';
import { ActionButton } from './ActionButton';
import { CorrectEntry } from './CorrectEntry';
import { ReverseEntry } from './ReverseEntry';

function AnswerValue({ answer }: { answer: Answer }) {
  if (answer.link)
    return (
      <a href={answer.link} target="_blank" rel="noreferrer" className={LINK}>
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
  if (!can('journal_entries:read')) return <span className="text-xs">{id}</span>;
  return (
    <Link to={`/journal/${id}`} className={`text-xs ${LINK}`}>
      {id}
    </Link>
  );
}

// What was asked, and answered
function Overview({ s }: { s: Submission }) {
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
    </div>
  );
}

// What it posted to Mifos: the entry live there first, then any it replaced or that reversed one
function JournalEntries({ s }: { s: Submission }) {
  // Newest first, as History is: they're listed as they were posted
  const entries = [...s.journal_entries].reverse();
  if (!entries.length) return <p className="text-sm text-muted-foreground">Nothing posted to Mifos yet.</p>;
  return (
    // One under another, a line between them, the one you're over shaded
    <div className="divide-y [&>*]:-mx-3 [&>*]:rounded-md [&>*]:p-3 [&>*]:transition-colors [&>*:hover]:bg-muted/50">
      {entries.map((e) => (
        <Entry key={e.transaction_id} e={e} live={e.transaction_id === s.live_entry} submission={s.id} />
      ))}
    </div>
  );
}

function Entry({ e, live, submission }: { e: JournalEntry; live: boolean; submission: string }) {
  const can = useCan();
  const corrections = useFlag('corrections');
  // One for both buttons: while either runs, neither starts another
  const correction = useCorrection(submission);
  return (
    <EntrySummary
      e={e}
      live={live}
      titled
      action={
        <>
          {live && can('journal_entries:edit') && (
            <>
              {corrections && <CorrectEntry e={e} correction={correction} />}
              <ReverseEntry transaction={e.transaction_id} correction={correction} />
            </>
          )}
          {can('journal_entries:read') && (
            <Button asChild variant="outline" size="sm">
              <Link to={`/journal/${e.transaction_id}`}>
                Go to journal entry <ArrowRight />
              </Link>
            </Button>
          )}
        </>
      }
    />
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
    <li className="relative rounded-r-md py-3 pr-3 pl-6 transition-colors hover:bg-muted/50">
      <span className="absolute top-[18px] -left-[5px] size-2.5 rounded-full border-2 border-foreground/40 bg-background" />
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

const DID: Record<ActionKind, string> = {
  done: 'Marked done',
  approve: 'Approved',
  disapprove: 'Disapproved',
  comment: 'Commented',
};

// Something a person did from Ourfos: who, when, what they said, and what they added
function Acted({ action }: { action: Action }) {
  return (
    <li className="relative rounded-r-md py-3 pr-3 pl-6 transition-colors hover:bg-muted/50">
      <span className="absolute top-[18px] -left-[5px] size-2.5 rounded-full border-2 border-foreground/40 bg-background" />
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">
          {(DID as Record<string, string | undefined>)[action.kind] ?? action.kind} by <Person email={action.by} />
        </span>
        <span className="ml-auto text-xs text-muted-foreground">
          <Time at={action.at} />
        </span>
      </div>
      <div className="mt-1 space-y-1 text-sm text-muted-foreground">
        {action.comment && <p>&ldquo;{action.comment}&rdquo;</p>}
        {action.files.length > 0 && (
          <p className="flex flex-wrap gap-x-3">
            {action.files.map((ref, n) => (
              <a key={ref} href={`/files?ref=${encodeURIComponent(ref)}`} className={LINK}>
                File {n + 1}
              </a>
            ))}
          </p>
        )}
      </div>
    </li>
  );
}

// Its runs and what people did, newest first, as a story
function History({ s }: { s: Submission }) {
  const story = [
    ...s.runs.map((r) => ({ at: r.started_at, item: <Event key={r.id} run={r} /> })),
    ...s.actions.map((a) => ({ at: a.at, item: <Acted key={a.id} action={a} /> })),
  ].sort((a, b) => (b.at ?? '').localeCompare(a.at ?? ''));
  return <ol className="ml-1.5 border-l pl-0">{story.map((x) => x.item)}</ol>;
}

// What you may do to it, now: mark a handed-over one done, and with approvals on, decide it or comment
function Actions({ form, s, noun }: { form: string; s: Submission; noun: string }) {
  const can = useCan();
  const approvals = useFlag('approvals');
  const action = useAction(form, s.id);
  const decided = s.status === 'approved' || s.status === 'disapproved';
  const kinds: ActionKind[] = [
    ...(s.status === 'handed_over' && can(`forms:${form}:resolve`) ? (['done'] as const) : []),
    ...(approvals && !decided && can(`forms:${form}:approve`) ? (['approve'] as const) : []),
    ...(approvals && !decided && can(`forms:${form}:disapprove`) ? (['disapprove'] as const) : []),
    ...(approvals && can(`forms:${form}:comment`) ? (['comment'] as const) : []),
  ];
  return kinds.map((kind) => (
    <ActionButton key={kind} kind={kind} noun={noun} reverses={s.live_entry} action={action} />
  ));
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
  const tests = useTests(form);
  const neighbours = useNeighbours({
    id,
    list: (cursor) => submissionQueries.list(form, cursor, tests),
    idOf: (row) => row.id,
    pathOf: (row) => `/forms/${form}/${row.id}`,
  });
  const { data: s, error, isPlaceholderData } = useSubmission(form, id);
  const spec = forms?.find((f) => f.key === form);
  const list = spec?.title ?? 'Back';
  const noun = spec ? spec.title.toLowerCase().replace(/s$/, '') : 'submission';
  // Requisitions post; anything else only if something of it has
  const posts = form === 'requisition' || (s?.journal_entries.length ?? 0) > 0;
  const [tab, setTab] = useTab(posts ? ['overview', 'journal', 'history'] : ['overview', 'history']);
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
        noun={noun}
        neighbours={neighbours}
        actions={s && !isPlaceholderData ? <Actions form={form} s={s} noun={noun} /> : undefined}
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
          <Tabs value={tab} onValueChange={setTab}>
            <RecordTabs>
              <RecordTab value="overview">Overview</RecordTab>
              {posts && (
                <RecordTab value="journal">
                  {s.journal_entries.length === 1 ? 'Journal entry' : 'Journal entries'} ({s.journal_entries.length})
                </RecordTab>
              )}
              <RecordTab value="history">History ({s.runs.length + s.actions.length})</RecordTab>
            </RecordTabs>
            <TabsContent value="overview" className="pt-6">
              <Overview s={s} />
            </TabsContent>
            {posts && (
              <TabsContent value="journal" className="pt-6">
                <JournalEntries s={s} />
              </TabsContent>
            )}
            <TabsContent value="history" className="pt-6">
              <History s={s} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
