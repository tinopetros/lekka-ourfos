import { CircleHelp, Loader2, Paperclip, Upload, X } from 'lucide-react';
import { useRef, useState } from 'react';
import { toast } from 'sonner';
import { Controller, type Control } from 'react-hook-form';
import {
  Field as FieldBox,
  FieldDescription,
  FieldError,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from '@/components/ui/field';
import { Button } from '@/components/ui/button';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import type { Field, Values } from './schema';

// Files, sent as they're picked, each listed by the name it was picked with, with a way to take it off again. On a
// phone, the camera is one way in. The button stands in for the browser's own picker, which says "No file chosen"
// however many there are
function Files({
  id,
  refs,
  names,
  upload,
  onChange,
}: {
  id: string;
  refs: string[];
  names: Record<string, string>;
  upload: (file: File) => Promise<string>;
  onChange: (refs: string[], named: Record<string, string>) => void;
}) {
  const [sending, setSending] = useState<{ key: string; name: string }[]>([]);
  const picker = useRef<HTMLInputElement>(null);
  return (
    <div className="space-y-2">
      {(refs.length > 0 || sending.length > 0) && (
        <ul className="space-y-1 text-sm">
          {refs.map((ref, i) => (
            <li key={ref} className="flex items-center gap-2">
              <Paperclip className="size-3.5 shrink-0 text-muted-foreground" />
              <span className="min-w-0 truncate">{names[ref] ?? `File ${String(i + 1)}`}</span>
              <button
                type="button"
                aria-label={`Take off ${names[ref] ?? `file ${String(i + 1)}`}`}
                className="ml-auto shrink-0 text-muted-foreground hover:text-foreground"
                onClick={() => {
                  onChange(
                    refs.filter((r) => r !== ref),
                    {},
                  );
                }}
              >
                <X className="size-4" />
              </button>
            </li>
          ))}
          {sending.map((s) => (
            <li key={s.key} className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="size-3.5 shrink-0 animate-spin" />
              <span className="min-w-0 truncate">Sending {s.name}…</span>
            </li>
          ))}
        </ul>
      )}
      <input
        ref={picker}
        id={id}
        type="file"
        multiple
        accept="image/*,application/pdf"
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => {
          const picked = Array.from(e.target.files ?? []).map((file) => ({ file, key: crypto.randomUUID() }));
          e.target.value = '';
          setSending((s) => [...s, ...picked.map((p) => ({ key: p.key, name: p.file.name }))]);
          void (async () => {
            const added: string[] = [];
            const named: Record<string, string> = {};
            for (const { file, key } of picked) {
              try {
                const ref = await upload(file);
                added.push(ref);
                named[ref] = file.name;
              } catch (error) {
                toast.error(error instanceof Error ? error.message : `Couldn't send ${file.name}`);
              } finally {
                setSending((s) => s.filter((x) => x.key !== key));
              }
            }
            if (added.length) onChange([...refs, ...added], named);
          })();
        }}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => {
          picker.current?.click();
        }}
      >
        <Upload /> Upload files
      </Button>
    </div>
  );
}

// A picture of where to find what it asks, on hover: one of the API's help images, in public/help
function Help({ image, title }: { image: string; title: string }) {
  return (
    <HoverCard openDelay={200}>
      <HoverCardTrigger asChild>
        <button type="button" aria-label={`Where to find the ${title.toLowerCase()}`} className="text-muted-foreground">
          <CircleHelp className="size-4" />
        </button>
      </HoverCardTrigger>
      <HoverCardContent className="w-[min(90vw,40rem)] p-1">
        <img src={`/help/${image}`} alt={`Where to find the ${title.toLowerCase()}`} className="rounded-md" />
      </HoverCardContent>
    </HoverCard>
  );
}

/** One question, as its kind asks it: its title, what it means, the input, and what's wrong with the answer */
export function FormField({
  field,
  name,
  control,
  upload,
  names,
  onNamed,
  onCommit,
}: {
  field: Field;
  name: string;
  control: Control<Values>;
  // Sends a picked file, its gs:// ref back
  upload: (file: File) => Promise<string>;
  // Each file's name as it was picked, by its ref: it's stored under a short one of its own
  names: Record<string, string>;
  onNamed: (named: Record<string, string>) => void;
  // An answer given without leaving its question, a choice or a file: the draft is saved then
  onCommit: () => void;
}) {
  if (field.kind === 'group') {
    return (
      <FieldSet>
        <FieldLegend variant="label">{field.title}</FieldLegend>
        {field.fields?.map((f) => (
          <FormField
            key={f.key}
            field={f}
            name={`${name}.${f.key}`}
            control={control}
            upload={upload}
            names={names}
            onNamed={onNamed}
            onCommit={onCommit}
          />
        ))}
      </FieldSet>
    );
  }
  const id = `field-${name}`;
  return (
    <Controller
      name={name}
      control={control}
      render={({ field: input, fieldState }) => {
        const value = typeof input.value === 'string' ? input.value : '';
        const invalid = fieldState.invalid;
        let asked;
        switch (field.kind) {
          case 'long':
            asked = <Textarea id={id} {...input} value={value} aria-invalid={invalid} rows={4} />;
            break;
          case 'amount':
            asked = (
              <div className="relative">
                <span className="absolute top-2 left-3 text-sm text-muted-foreground">$</span>
                <Input
                  id={id}
                  {...input}
                  value={value}
                  aria-invalid={invalid}
                  type="number"
                  inputMode="decimal"
                  step="0.01"
                  min={0}
                  className="pl-6"
                />
              </div>
            );
            break;
          case 'integer':
            asked = (
              <Input
                id={id}
                {...input}
                value={value}
                aria-invalid={invalid}
                type="number"
                inputMode="numeric"
                step="1"
                min={field.min}
              />
            );
            break;
          case 'date':
            asked = <Input id={id} {...input} value={value} aria-invalid={invalid} type="date" />;
            break;
          case 'link':
            asked = <Input id={id} {...input} value={value} aria-invalid={invalid} type="url" inputMode="url" />;
            break;
          case 'choice':
            asked = (
              <Select
                value={value}
                onValueChange={(v) => {
                  input.onChange(v);
                  onCommit();
                }}
              >
                <SelectTrigger id={id} aria-invalid={invalid} onBlur={input.onBlur} ref={input.ref} className="w-full">
                  <SelectValue placeholder="Choose one" />
                </SelectTrigger>
                <SelectContent>
                  {field.options?.map((o) => (
                    <SelectItem key={o} value={o}>
                      {o}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            );
            break;
          case 'files':
            asked = (
              <Files
                id={id}
                refs={Array.isArray(input.value) ? (input.value as string[]) : []}
                names={names}
                upload={upload}
                onChange={(refs, named) => {
                  onNamed(named);
                  input.onChange(refs);
                  onCommit();
                }}
              />
            );
            break;
          default:
            asked = <Input id={id} {...input} value={value} aria-invalid={invalid} />;
        }
        return (
          <FieldBox data-invalid={invalid}>
            <div className="flex items-center gap-2">
              <FieldLabel htmlFor={id}>
                {field.title}
                {field.required && <span className="text-destructive">*</span>}
              </FieldLabel>
              {field.helpImage && <Help image={field.helpImage} title={field.title} />}
            </div>
            {field.description && <FieldDescription>{field.description}</FieldDescription>}
            {asked}
            <FieldError errors={[fieldState.error]} />
          </FieldBox>
        );
      }}
    />
  );
}
