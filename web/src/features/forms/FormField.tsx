import { CircleHelp, Loader2, Paperclip, X } from 'lucide-react';
import { useState } from 'react';
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
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import type { Field, Values } from './schema';

// A file's name, as it was picked: its stored name has a short tag before it, to keep two of the same name apart
function fileName(ref: string): string {
  return (ref.split('/').pop() ?? ref).replace(/^[0-9a-f]{8}-/, '');
}

// Files, sent as they're picked, each listed with a way to take it off again. On a phone, the camera is one way in
function Files({
  id,
  refs,
  upload,
  onChange,
}: {
  id: string;
  refs: string[];
  upload: (file: File) => Promise<string>;
  onChange: (refs: string[]) => void;
}) {
  const [sending, setSending] = useState<string[]>([]);
  return (
    <div className="space-y-2">
      {refs.length > 0 && (
        <ul className="space-y-1 text-sm">
          {refs.map((ref) => (
            <li key={ref} className="flex items-center gap-2">
              <Paperclip className="size-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate">{fileName(ref)}</span>
              <button
                type="button"
                aria-label={`Take off ${fileName(ref)}`}
                className="ml-auto text-muted-foreground hover:text-foreground"
                onClick={() => {
                  onChange(refs.filter((r) => r !== ref));
                }}
              >
                <X className="size-4" />
              </button>
            </li>
          ))}
          {sending.map((name) => (
            <li key={name} className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" /> {name}
            </li>
          ))}
        </ul>
      )}
      <Input
        id={id}
        type="file"
        multiple
        accept="image/*,application/pdf"
        onChange={(e) => {
          const picked = Array.from(e.target.files ?? []);
          e.target.value = '';
          setSending((s) => [...s, ...picked.map((f) => f.name)]);
          void (async () => {
            const added: string[] = [];
            for (const file of picked) {
              try {
                added.push(await upload(file));
              } catch (error) {
                toast.error(error instanceof Error ? error.message : `Couldn't send ${file.name}`);
              } finally {
                setSending((s) => s.filter((n) => n !== file.name));
              }
            }
            if (added.length) onChange([...refs, ...added]);
          })();
        }}
      />
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
  onCommit,
}: {
  field: Field;
  name: string;
  control: Control<Values>;
  // Sends a picked file, its gs:// ref back
  upload: (file: File) => Promise<string>;
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
                upload={upload}
                onChange={(refs) => {
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
