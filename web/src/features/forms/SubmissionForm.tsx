import { zodResolver } from '@hookform/resolvers/zod';
import { useCallback, useMemo, useRef, useState } from 'react';
import { useForm, type FieldErrors, type Resolver } from 'react-hook-form';
import { Link, useNavigate } from 'react-router';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { FieldGroup } from '@/components/ui/field';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { ApiError } from '@/lib/api/client';
import { useCan, useForms } from '@/lib/api/queries';
import { upload, useDiscard, useSaveDraft, useSubmit } from './api';
import { FormField } from './FormField';
import { blank, fields, message, toAnswers, validator, type Field, type Values } from './schema';

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

  const resolver = useMemo<Resolver<Values>>(() => {
    const check = zodResolver(validator(form) as never, { error: message } as never) as unknown as Resolver<Values>;
    return (values, context, options) => check(toAnswers(fs, values), context, options);
  }, [form, fs]);
  const { control, handleSubmit, setError, setFocus, getValues, formState } = useForm<Values>({
    defaultValues: draft ? restore(fs, draft) : blank(fs),
    resolver,
    mode: 'onTouched',
  });
  const wrong = problems(fs, formState.errors);
  const whole = formState.errors.root?.message;

  // What was last saved, or what the form started with: leaving a question you didn't change saves nothing, and a
  // new form's own prefilled answers aren't worth a draft
  const last = useRef(JSON.stringify({ values: getValues(), test: draftTest }));
  const submitted = useRef(false);
  const keep = useCallback(
    (nextTest = test) => {
      if (submitted.current) return;
      const values = getValues();
      const now = JSON.stringify({ values, test: nextTest });
      if (now === last.current) return;
      last.current = now;
      setSaved('saving');
      save.mutate(
        { values, test: nextTest },
        {
          onSuccess: () => {
            setSaved('saved');
            if (!isDraft) {
              setIsDraft(true);
              // The same page, now the draft's: a link to it opens it again
              void navigate(`/forms/${form}/${id}`, { replace: true });
            }
          },
          onError: () => {
            setSaved('failed');
            last.current = '';
          },
        },
      );
    },
    [test, getValues, isDraft, save, navigate, form, id],
  );

  if (!fs.length) return <p className="p-6 text-muted-foreground">There's no form {form}</p>;
  const list = spec?.title ?? form;
  const noun = list.toLowerCase().replace(/s$/, '');

  const onValid = (answers: Values) => {
    submitted.current = true;
    submit.mutate(
      { answers, test },
      {
        onSuccess: () => {
          onSubmitted?.();
          void navigate(`/forms/${form}/${id}`, { replace: true });
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
        <h1 className="text-lg font-semibold">New {noun}</h1>
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
              {isDraft && (
                <Dialog>
                  <DialogTrigger asChild>
                    <Button type="button" variant="ghost">
                      Discard
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Discard this draft?</DialogTitle>
                      <DialogDescription>Its answers and any files added to it go for good.</DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                      <DialogClose asChild>
                        <Button variant="outline">Keep it</Button>
                      </DialogClose>
                      <Button
                        variant="destructive"
                        disabled={discard.isPending}
                        onClick={() => {
                          submitted.current = true;
                          discard.mutate(undefined, {
                            onSuccess: () => void navigate(`/forms/${form}`, { replace: true }),
                          });
                        }}
                      >
                        Discard
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              )}
              <Button type="submit" disabled={submit.isPending}>
                {submit.isPending ? 'Submitting…' : 'Submit'}
              </Button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}
