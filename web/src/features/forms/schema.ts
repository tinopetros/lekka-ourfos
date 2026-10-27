import * as z from 'zod';
import schemas from '@/lib/api/forms.json';

// A form's questions, from the JSON Schema its Pydantic model makes (make types). The form is drawn from these, and
// checked by zod made from the same schema: what the API will check, before it's sent

export type Kind = 'text' | 'long' | 'amount' | 'integer' | 'date' | 'choice' | 'link' | 'files' | 'group';

export interface Field {
  key: string;
  title: string;
  description?: string;
  kind: Kind;
  required: boolean;
  options?: string[];
  min?: number;
  prefill?: 'today';
  helpImage?: string;
  // A group's own questions, e.g. a requisition's files
  fields?: Field[];
}

interface Schema {
  type?: string;
  title?: string;
  description?: string;
  format?: string;
  pattern?: string;
  enum?: string[];
  // A choice of one: Pydantic's Literal with a single option
  const?: string;
  minimum?: number;
  exclusiveMinimum?: number;
  anyOf?: Schema[];
  $ref?: string;
  $defs?: Record<string, Schema>;
  properties?: Record<string, Schema>;
  required?: string[];
  kind?: string;
  prefill?: 'today';
  help_image?: string;
}

const SCHEMAS = schemas as Record<string, Schema>;

export const formKeys = Object.keys(SCHEMAS);

// An optional answer is its type or null: what it is when answered
function answered(prop: Schema): Schema {
  return prop.anyOf?.find((s) => s.type !== 'null') ?? prop;
}

function kindOf(prop: Schema, inner: Schema): Kind {
  const kind = prop.kind ?? inner.kind;
  if (kind === 'long' || kind === 'amount' || kind === 'files') return kind;
  if (inner.properties) return 'group';
  if (inner.enum ?? inner.const) return 'choice';
  if (inner.format === 'date') return 'date';
  if (inner.type === 'integer') return 'integer';
  if (inner.type === 'number') return 'amount';
  if (inner.pattern?.startsWith('^https://')) return 'link';
  return 'text';
}

function fieldsOf(schema: Schema, defs: Record<string, Schema>): Field[] {
  return Object.entries(schema.properties ?? {}).map(([key, prop]) => {
    let inner = answered(prop);
    if (inner.$ref) inner = defs[inner.$ref.split('/').pop() ?? ''] ?? inner;
    const kind = kindOf(prop, inner);
    return {
      key,
      title: prop.title ?? inner.title ?? key,
      description: prop.description ?? inner.description,
      kind,
      required: schema.required?.includes(key) ?? false,
      options: inner.enum ?? (inner.const === undefined ? undefined : [inner.const]),
      min: inner.minimum,
      prefill: prop.prefill ?? inner.prefill,
      helpImage: prop.help_image ?? inner.help_image,
      fields: kind === 'group' ? fieldsOf(inner, defs) : undefined,
    };
  });
}

export function fields(form: string): Field[] {
  const schema = SCHEMAS[form];
  return schema ? fieldsOf(schema, schema.$defs ?? {}) : [];
}

// What a form holds while it's being filled in: text, as inputs give it, or a group's own values
export type Values = Record<string, unknown>;

function today(): string {
  const d = new Date();
  return `${String(d.getFullYear())}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function blank(fs: Field[]): Values {
  return Object.fromEntries(
    fs.map((f) => [
      f.key,
      f.kind === 'group'
        ? blank(f.fields ?? [])
        : f.kind === 'files'
          ? []
          : f.prefill === 'today'
            ? today()
            : // A question with only one answer has it already
              f.required && f.options?.length === 1
              ? f.options[0]
              : '',
    ]),
  );
}

/** What was typed, as the API takes it: numbers as numbers, and an answer left empty left out */
export function toAnswers(fs: Field[], values: Values): Values {
  const answers: Values = {};
  for (const f of fs) {
    const value = values[f.key];
    if (f.kind === 'group') answers[f.key] = toAnswers(f.fields ?? [], (value ?? {}) as Values);
    else if (f.kind === 'files') answers[f.key] = value ?? [];
    else if (value === undefined || value === null || (typeof value === 'string' && value.trim() === '')) continue;
    else if (f.kind === 'amount' || f.kind === 'integer') answers[f.key] = Number(value);
    else answers[f.key] = typeof value === 'string' ? value.trim() : value;
  }
  return answers;
}

export function validator(form: string): z.ZodType {
  return z.fromJSONSchema(SCHEMAS[form] as Parameters<typeof z.fromJSONSchema>[0]);
}

/** What's wrong, in words for whoever's filling it in, not a schema's */
export function message(issue: z.core.$ZodRawIssue): string | undefined {
  if (issue.input === undefined) return 'Required';
  switch (issue.code) {
    case 'not_multiple_of':
      return 'To the cent: at most 2 decimal places';
    case 'too_small':
      return issue.origin === 'string' ? 'Required' : `At least ${String(issue.minimum)}`;
    case 'invalid_value':
      return 'Choose one of the options';
    case 'invalid_format':
      return issue.format === 'regex' ? "That's not the link it asks for" : 'Not a date';
    case 'invalid_type':
      return issue.expected === 'number' || issue.expected === 'int' ? 'A number' : undefined;
    default:
      return undefined;
  }
}
