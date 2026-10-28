import { zodResolver } from '@hookform/resolvers/zod';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useForm, type FieldErrors, type Resolver } from 'react-hook-form';
import { Loader2 } from 'lucide-react';
import { Link, useNavigate } from 'react-router';
import { toast } from 'sonner';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { FieldGroup } from '@/components/ui/field';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import type { KeepScroll } from '@/app/useScrollArea';
import { ApiError, type Problem } from '@/lib/api/client';
import { useCan, useForms } from '@/lib/api/queries';
import { upload, useDiscard, useSaveDraft, useSubmit } from './api';
import { FormField } from './FormField';
import { blank, fields, message, toAnswers, validator, type Field, type Values } from './schema';

// Where a draft keeps its files' names as picked: beside its answers, never one of them
const NAMES = '_file_names';

// Every problem the form has, each with the title of the question it's about, for the summary at the top
function problems(
  fs: Field[],
  errors: FieldErrors<Values>,
  prefix = '',
): { name: string; title: string; message: string }[] {
  return fs.flatMap((f) => {
    const error = errors[f.key] as FieldErrors<Values> | { message?: string } | undefined;
    if (!error) return [];
    if (f.kind === 'group') return problems(f.fields ?? [], error, `${prefix}${f.key}.`);
    const text = (error as { message?: string }).message;
    return text ? [{ name: `${prefix}${f.key}`, title: f.title, message: text }] : [];
  });
}

// Every question's name, a group's as group.question
function names(fs: Field[], prefix = ''): string[] {
  return fs.flatMap((f) => (f.kind === 'group' ? names(f.fields ?? [], `${prefix}${f.key}.`) : [`${prefix}${f.key}`]));
}

// A saved draft over the blank form, a group's answers into its group: a question added since keeps its blank
function restore(fs: Field[], saved: Values): Values {
  const values = blank(fs);
  for (const f of fs) {
    const v = saved[f.key];
    if (v === undefined) continue;
    values[f.key] =
      f.kind === 'group' && typeof v === 'object' && v !== null ? restore(f.fields ?? [], v as Values) : v;
  }
  return values;
}

function Saved({ state }: { state: 'idle' | 'saving' | 'saved' | 'failed' }) {
  const text = { idle: '', saving: 'Saving…', saved: 'Draft saved', failed: 'Not saved' }[state];
  return (
    <span
      className={state === 'failed' ? 'text-sm text-destructive' : 'text-sm text-muted-foreground'}
      aria-live="polite"
    >
      {text}
    </span>
  );
}

// Amber, as drafts are everywhere: waiting on you, to submit or discard
function DraftBadge() {
  return (
    <Badge
      variant="outline"
      className="border-amber-400 bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
    >
      draft
    </Badge>
  );
}

/** One of our own forms, being filled in: drawn from its schema, saved as a draft as you go, checked as the API
 * will check it, then submitted. New, or a draft opened again */
export function SubmissionForm({
  form,
  id,
  draft,
  draftTest = false,
  onSubmitted,
}: {
  form: string;
  id: string;
  draft?: Values | null;
  draftTest?: boolean;
  // So the page shows the record, not the form, once it's submitted
  onSubmitted?: () => void;
}) {
  const navigate = useNavigate();
  const { data: forms } = useForms();
  const can = useCan();
  const spec = forms?.find((f) => f.key === form);
  const fs = useMemo(() => fields(form), [form]);
  const [test, setTest] = useState(draftTest);
  const submit = useSubmit(form, id);
  const save = useSaveDraft(form, id);
  const discard = useDiscard(form, id);
  // A draft until it's submitted: one there already, or one made by the first save
  const [isDraft, setIsDraft] = useState(Boolean(draft));
  const [saved, setSaved] = useState<'idle' | 'saving' | 'saved' | 'failed'>(draft ? 'saved' : 'idle');
  const [confirming, setConfirming] = useState(false);

  const resolver = useMemo<Resolver<Values>>(() => {
    const check = zodResolver(validator(form) as never, { error: message } as never) as unknown as Resolver<Values>;
    return (values, context, options) => check(toAnswers(fs, values), context, options);
  }, [form, fs]);
  const { control, handleSubmit, setError, clearErrors, getFieldState, setFocus, getValues, formState } =
    useForm<Values>({
      defaultValues: draft ? restore(fs, draft) : blank(fs),
      resolver,
      mode: 'onTouched',
    });
  const wrong = problems(fs, formState.errors);
  const whole = formState.errors.root?.message;

  // What was last saved, or what the form started with: leaving a question you didn't change saves nothing, and a
  // new form's own prefilled answers aren't worth a draft
  // Each file's name as picked, kept with the draft alone: what's submitted, and stored, names it afresh
  const [fileNames, setFileNames] = useState<Record<string, string>>(
    () => (draft?.[NAMES] as Record<string, string> | undefined) ?? {},
  );
  const picked = useRef(fileNames);
  const named = (more: Record<string, string>) => {
    picked.current = { ...picked.current, ...more };
    setFileNames(picked.current);
  };
  const snapshot = useCallback(() => ({ ...getValues(), [NAMES]: picked.current }), [getValues]);
  const last = useRef(JSON.stringify({ values: { ...getValues(), [NAMES]: fileNames }, test: draftTest }));
  const submitted = useRef(false);

  // What the API found as the draft saved, on the questions it's about that you've been to. A problem gone since is
  // cleared; what the browser found itself is left as it is
  const show = useCallback(
    (found: Problem[]) => {
      const wrong = new Map(found.map((p) => [p.loc.join('.'), p.msg]));
      for (const name of names(fs)) {
        const { isTouched, error } = getFieldState(name);
        const message = wrong.get(name);
        if (message && isTouched && (!error || error.type === 'api')) setError(name, { type: 'api', message });
        else if (!message && error?.type === 'api') clearErrors(name);
      }
    },
    [fs, getFieldState, setError, clearErrors],
  );

  const keep = useCallback(
    (nextTest = test, then?: () => void) => {
      if (submitted.current) return;
      const values = snapshot();
      const now = JSON.stringify({ values, test: nextTest });
      if (now === last.current) {
        then?.();
        return;
      }
      last.current = now;
      setSaved('saving');
      save.mutate(
        { values, answers: toAnswers(fs, values), test: nextTest },
        {
          onSuccess: (saved) => {
            setSaved('saved');
            show(saved.problems);
            if (!isDraft) {
              setIsDraft(true);
              // The same page, now the draft's: a link to it opens it again
              void navigate(`/forms/${form}/${id}`, {
                replace: true,
                state: { keepScroll: true } satisfies KeepScroll,
              });
            }
            then?.();
          },
          onError: () => {
            setSaved('failed');
            last.current = '';
          },
        },
      );
    },
    [test, snapshot, isDraft, save, navigate, form, id, fs, show],
  );

  // Leaving the page: what's in the question you're on, if it changed, is saved as the page goes. keepalive, so the
  // browser sends it even after the tab's closed. Hidden, on a phone, it's saved the usual way: the page may not
  // come back
  useEffect(() => {
    const hidden = () => {
      if (document.visibilityState === 'hidden') keep();
    };
    const leaving = () => {
      if (submitted.current) return;
      const values = snapshot();
      const now = JSON.stringify({ values, test });
      if (now === last.current) return;
      last.current = now;
      void fetch(`/api/forms/${form}/submissions/${id}`, {
        method: 'PUT',
        keepalive: true,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ values, test }),
      });
    };
    document.addEventListener('visibilitychange', hidden);
    window.addEventListener('pagehide', leaving);
    return () => {
      document.removeEventListener('visibilitychange', hidden);
      window.removeEventListener('pagehide', leaving);
    };
  }, [keep, snapshot, test, form, id]);

  if (!fs.length) return <p className="p-6 text-muted-foreground">There's no form {form}</p>;
  const list = spec?.title ?? form;
  const noun = list.toLowerCase().replace(/s$/, '');
  const Noun = noun.charAt(0).toUpperCase() + noun.slice(1);
  const record = `/forms/${form}/${id}`;

  // Done with it, one way or another: back to the list, saving nothing more on the way out, and a toast saying
  // what happened, with a way back to it where there's something to go back to
  const leave = (said?: string, open?: string) => {
    submitted.current = true;
    void navigate(`/forms/${form}`, { replace: true });
    if (said) toast.success(said, open ? { action: { label: 'View', onClick: () => void navigate(open) } } : undefined);
  };

  const onValid = (answers: Values) => {
    submitted.current = true;
    submit.mutate(
      { answers, test },
      {
        onSuccess: (done) => {
          onSubmitted?.();
          leave(`${Noun} #${String(done.response_number)} submitted`, record);
        },
        onError: (error) => {
          submitted.current = false;
          // What only the API could check, like an odometer going backwards, by its field, or for the whole form
          if (!(error instanceof ApiError)) return;
          const known = new Set(names(fs));
          error.problems.forEach((p, i) => {
            const name = p.loc.join('.');
            const text = p.msg.replace(/^Value error, /, '');
            // The first problem's question takes the focus, so you're taken to it
            if (known.has(name)) setError(name, { type: 'api', message: text }, { shouldFocus: i === 0 });
            else setError('root', { type: 'api', message: text });
          });
          if (!error.problems.some((p) => known.has(p.loc.join('.')))) window.scrollTo({ top: 0, behavior: 'smooth' });
        },
      },
    );
  };

  return (
    <div className="mx-auto max-w-2xl pb-16">
      <Breadcrumb className="mb-4">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to={`/forms/${form}`}>{list}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{isDraft ? 'Draft' : 'New'}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="mb-6 flex items-baseline justify-between gap-4">
        <div className="flex items-center gap-2">
          <h1 className="text-lg font-semibold">New {noun}</h1>
          {isDraft && <DraftBadge />}
        </div>
        <Saved state={saved} />
      </div>
      {!can(`forms:${form}:submit`) ? (
        <p className="text-muted-foreground">You can't submit a {noun}.</p>
      ) : (
        <form
          onSubmit={(e) => void handleSubmit(onValid)(e)}
          // Leaving a question saves the draft, if it changed
          onBlurCapture={() => {
            keep();
          }}
          noValidate
          className="space-y-6"
        >
          {(wrong.length > 0 || whole) && formState.isSubmitted && (
            <div role="alert" className="rounded-lg border border-destructive/50 p-4 text-sm">
              <p className="mb-2 font-medium text-destructive">Some answers need another look</p>
              <ul className="ml-4 list-disc space-y-1">
                {whole && <li>{whole}</li>}
                {wrong.map((w) => (
                  <li key={w.name}>
                    <button
                      type="button"
                      className="underline underline-offset-2"
                      onClick={() => {
                        setFocus(w.name);
                      }}
                    >
                      {w.title}
                    </button>
                    : {w.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <FieldGroup>
            {fs.map((f) => (
              <FormField
                key={f.key}
                field={f}
                name={f.key}
                control={control}
                upload={(file) => upload(form, id, file)}
                names={fileNames}
                onNamed={named}
                onCommit={() => {
                  keep();
                }}
              />
            ))}
          </FieldGroup>
          <div className="flex flex-wrap items-center justify-between gap-4 border-t pt-4">
            {can(`forms:${form}:test`) ? (
              <div className="flex items-center gap-2">
                <Switch
                  id="test"
                  checked={test}
                  onCheckedChange={(on) => {
                    setTest(on);
                    keep(on);
                  }}
                />
                <Label htmlFor="test">Test: never posted, and marked as a test in its emails</Label>
              </div>
            ) : (
              <span />
            )}
            <div className="flex items-center gap-2">
              <Dialog open={confirming} onOpenChange={setConfirming}>
                <Button
                  type="button"
                  variant="destructive"
                  // The question you're on keeps its focus: leaving it would save a draft you're about to discard
                  onMouseDown={(e) => {
                    e.preventDefault();
                  }}
                  onClick={() => {
                    // Nothing typed, nothing saved: there's nothing to lose, so no asking
                    if (!isDraft && JSON.stringify({ values: snapshot(), test }) === last.current) leave();
                    else setConfirming(true);
                  }}
                >
                  Discard
                </Button>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Discard this {isDraft ? 'draft' : noun}?</DialogTitle>
                    <DialogDescription>
                      {isDraft ? 'Its answers and any files added to it go for good.' : "What you've typed goes."}
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <DialogClose asChild>
                      <Button variant="outline">Keep it</Button>
                    </DialogClose>
                    <Button
                      variant="destructive"
                      disabled={discard.isPending}
                      onClick={() => {
                        if (!isDraft) {
                          leave(`${Noun} discarded`);
                          return;
                        }
                        submitted.current = true;
                        discard.mutate(undefined, {
                          onSuccess: () => {
                            leave(`${Noun} draft discarded`);
                          },
                        });
                      }}
                    >
                      {discard.isPending ? 'Discarding…' : 'Discard'}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
              <Button
                type="button"
                variant="outline"
                // Saved, and back to the list: drafts wait there, in Your drafts
                onClick={() => {
                  keep(test, () => {
                    leave(`${Noun} saved as a draft`, record);
                  });
                }}
              >
                Save draft
              </Button>
              <Button type="submit" variant="success" disabled={submit.isPending}>
                {submit.isPending && <Loader2 className="animate-spin" />}
                {submit.isPending ? 'Submitting…' : 'Submit'}
              </Button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}
