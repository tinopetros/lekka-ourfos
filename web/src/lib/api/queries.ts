import { keepPreviousData, queryOptions, useQuery } from '@tanstack/react-query';
import { api, unwrap } from './client';
import type { SubmissionSummary } from './types';

export const PAGE_SIZE = 25;

/** Every query's key and fetch in one place, so a page and a prefetch ask for the same thing the same way. */
export const queries = {
  me: () => queryOptions({ queryKey: ['me'], queryFn: () => unwrap(api.GET('/api/me')), staleTime: Infinity }),
  forms: () => queryOptions({ queryKey: ['forms'], queryFn: () => unwrap(api.GET('/api/forms')), staleTime: Infinity }),
  submissions: (form: string, cursor?: string) =>
    queryOptions({
      queryKey: ['submissions', form, cursor ?? null],
      queryFn: () =>
        unwrap(
          api.GET('/api/forms/{form}/submissions', { params: { path: { form }, query: { cursor, limit: PAGE_SIZE } } }),
        ),
    }),
  submission: (form: string, id: string) =>
    queryOptions({
      queryKey: ['submission', form, id],
      queryFn: () => unwrap(api.GET('/api/forms/{form}/submissions/{id}', { params: { path: { form, id } } })),
    }),
  journalEntries: (cursor?: string) =>
    queryOptions({
      queryKey: ['journal_entries', cursor ?? null],
      queryFn: () => unwrap(api.GET('/api/journal_entries', { params: { query: { cursor, limit: PAGE_SIZE } } })),
    }),
  journalEntry: (id: string) =>
    queryOptions({
      queryKey: ['journal_entry', id],
      queryFn: () =>
        unwrap(api.GET('/api/journal_entries/{transaction_id}', { params: { path: { transaction_id: id } } })),
    }),
};

export const useMe = () => useQuery(queries.me());
export const useForms = () => useQuery(queries.forms());

// The page you were on stays while the next one loads
export const useSubmissions = (form: string, cursor?: string) =>
  useQuery({ ...queries.submissions(form, cursor), placeholderData: keepPreviousData });

export const useJournalEntries = (cursor?: string) =>
  useQuery({ ...queries.journalEntries(cursor), placeholderData: keepPreviousData });

/** The sheet opens at once with the row it was opened from, and fills in the rest when it comes. */
export const useSubmission = (form: string, id: string, row?: SubmissionSummary) =>
  useQuery({
    ...queries.submission(form, id),
    placeholderData: row && { ...row, answers: [], raw: null, runs: [], journal_entries: [] },
  });

export const useJournalEntry = (id: string) => useQuery(queries.journalEntry(id));
