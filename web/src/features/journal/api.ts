import { keepPreviousData, queryOptions, useQuery } from '@tanstack/react-query';
import { api, unwrap } from '@/lib/api/client';
import { PAGE_SIZE } from '@/lib/api/queries';

export const journalQueries = {
  list: (cursor?: string, tests = false) =>
    queryOptions({
      queryKey: ['journal_entries', cursor ?? null, tests],
      queryFn: () =>
        unwrap(api.GET('/api/journal_entries', { params: { query: { cursor, limit: PAGE_SIZE, tests } } })),
    }),
  one: (id: string) =>
    queryOptions({
      queryKey: ['journal_entry', id],
      queryFn: () =>
        unwrap(api.GET('/api/journal_entries/{transaction_id}', { params: { path: { transaction_id: id } } })),
    }),
};

// The page you were on stays while the next one loads
export const useJournalEntries = (cursor?: string, tests = false) =>
  useQuery({ ...journalQueries.list(cursor, tests), placeholderData: keepPreviousData });

export const useJournalEntry = (id: string) => useQuery(journalQueries.one(id));
