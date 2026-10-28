import { keepPreviousData, queryOptions, useQuery } from '@tanstack/react-query';
import { api, unwrap } from '@/lib/api/client';
import { PAGE_SIZE } from '@/lib/api/queries';
import type { SubmissionSummary } from '@/lib/api/types';

export const submissionQueries = {
  list: (form: string, cursor?: string) =>
    queryOptions({
      queryKey: ['submissions', form, cursor ?? null],
      queryFn: () =>
        unwrap(
          api.GET('/api/forms/{form}/submissions', { params: { path: { form }, query: { cursor, limit: PAGE_SIZE } } }),
        ),
    }),
  one: (form: string, id: string) =>
    queryOptions({
      queryKey: ['submission', form, id],
      queryFn: () => unwrap(api.GET('/api/forms/{form}/submissions/{id}', { params: { path: { form, id } } })),
    }),
};

// The page you were on stays while the next one loads
export const useSubmissions = (form: string, cursor?: string) =>
  useQuery({ ...submissionQueries.list(form, cursor), placeholderData: keepPreviousData });

// The sheet opens at once with the row it was opened from, and fills in the rest when it comes
export const useSubmission = (form: string, id: string, row?: SubmissionSummary) =>
  useQuery({
    ...submissionQueries.one(form, id),
    placeholderData: row && { ...row, answers: [], raw: null, runs: [], journal_entries: [], draft: null },
  });
