import type { components } from './schema';

// The API's models by name, generated from its Pydantic models (docs/phase13/adr.md 4). Never written by hand
type Schemas = components['schemas'];
export type Me = Schemas['Me'];
export type FormInfo = Schemas['FormInfo'];
export type SubmissionSummary = Schemas['SubmissionSummary'];
export type Submission = Schemas['Submission'];
export type Answer = Schemas['Answer'];
export type Run = Schemas['Run'];
export type Line = Schemas['Line'];
export type JournalEntry = Schemas['JournalEntry'];
