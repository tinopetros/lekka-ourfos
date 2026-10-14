import type { components } from './schema';

// The API's models by name, generated from its Pydantic models. Never written by hand
type Schemas = components['schemas'];
export type Me = Schemas['Me'];
export type FormInfo = Schemas['FormInfo'];
export type SubmissionSummary = Schemas['SubmissionSummary'];
export type Submission = Schemas['Submission'];
export type Answer = Schemas['Answer'];
export type Run = Submission['runs'][number];
export type ExpenseRun = Schemas['ExpenseRun'];
export type CorrectionRun = Schemas['CorrectionRun'];
export type Line = Schemas['Line'];
export type JournalEntry = Schemas['JournalEntry'];
