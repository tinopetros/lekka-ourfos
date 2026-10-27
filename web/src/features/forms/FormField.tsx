import { CircleHelp } from 'lucide-react';
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
export function FormField({ field, name, control }: { field: Field; name: string; control: Control<Values> }) {
  if (field.kind === 'group') {
    return (
      <FieldSet>
        <FieldLegend variant="label">{field.title}</FieldLegend>
        {field.fields?.map((f) => (
          <FormField key={f.key} field={f} name={`${name}.${f.key}`} control={control} />
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
              <Select value={value} onValueChange={input.onChange}>
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
            // Uploads come with drafts: a file is sent as it's picked, under the draft's id
            asked = (
              <p id={id} className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                Adding files here is coming next
              </p>
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
