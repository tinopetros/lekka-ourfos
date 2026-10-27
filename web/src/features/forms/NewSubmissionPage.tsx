import { zodResolver } from '@hookform/resolvers/zod';
import { useMemo, useState } from 'react';
import { useForm, type FieldErrors, type Resolver } from 'react-hook-form';
import { Link, useNavigate, useParams } from 'react-router';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import { Button } from '@/components/ui/button';
import { FieldGroup } from '@/components/ui/field';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { ApiError } from '@/lib/api/client';
import { useCan, useForms } from '@/lib/api/queries';
import { useSubmit } from './api';
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

/** A new submission of one of our own forms: drawn from its schema, checked as the API will, then sent */
export function NewSubmissionPage() {
  const { form = '' } = useParams();
  const navigate = useNavigate();
  const { data: forms } = useForms();
  const can = useCan();
  const spec = forms?.find((f) => f.key === form);
  const fs = useMemo(() => fields(form), [form]);
  // The submission's id, made here: sending it again, after a dropped connection, is sending it once
  const [id] = useState(() => crypto.randomUUID());
  const [test, setTest] = useState(false);
  const submit = useSubmit(form, id);

  const resolver = useMemo<Resolver<Values>>(() => {
    const check = zodResolver(validator(form) as never, { error: message } as never) as unknown as Resolver<Values>;
    return (values, context, options) => check(toAnswers(fs, values), context, options);
  }, [form, fs]);
  const { control, handleSubmit, setError, setFocus, formState } = useForm<Values>({
    defaultValues: blank(fs),
    resolver,
    mode: 'onTouched',
  });
  const wrong = problems(fs, formState.errors);
  const whole = formState.errors.root?.message;

  if (!fs.length) return <p className="p-6 text-muted-foreground">There's no form {form}</p>;
  const list = spec?.title ?? form;
  const noun = list.toLowerCase().replace(/s$/, '');

  const send = handleSubmit((answers) => {
    submit.mutate(
      { answers, test },
      {
        onSuccess: () => void navigate(`/forms/${form}/${id}`, { replace: true }),
        onError: (error) => {
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
  });

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
            <BreadcrumbPage>New</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <h1 className="mb-6 text-lg font-semibold">New {noun}</h1>
      {!can(`forms:${form}:submit`) ? (
        <p className="text-muted-foreground">You can't submit a {noun}.</p>
      ) : (
        <form onSubmit={(e) => void send(e)} noValidate className="space-y-6">
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
              <FormField key={f.key} field={f} name={f.key} control={control} />
            ))}
          </FieldGroup>
          <div className="flex items-center justify-between gap-4 border-t pt-4">
            {can(`forms:${form}:test`) ? (
              <div className="flex items-center gap-2">
                <Switch id="test" checked={test} onCheckedChange={setTest} />
                <Label htmlFor="test">Test: never posted, and marked as a test in its emails</Label>
              </div>
            ) : (
              <span />
            )}
            <Button type="submit" disabled={submit.isPending}>
              {submit.isPending ? 'Submitting…' : 'Submit'}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
