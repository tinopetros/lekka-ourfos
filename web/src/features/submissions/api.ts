import { keepPreviousData, queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, unwrap } from '@/lib/api/client';
import { toast } from 'sonner';
import { PAGE_SIZE } from '@/lib/api/queries';
import type { SubmissionSummary } from '@/lib/api/types';
import type { components } from '@/lib/api/schema';

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

// The sheet opens at once with the row it was opened from, and fills in the rest when it comes. Off until there's
// one to fetch
export const useSubmission = (form: string, id: string, row?: SubmissionSummary, enabled = true) =>
  useQuery({
    ...submissionQueries.one(form, id),
    enabled,
    placeholderData: row && { ...row, answers: [], raw: null, runs: [], journal_entries: [], draft: null },
  });

// How often, and how long, a correction's run is watched: a cold start and Mifos can take a minute or two
const EVERY = 2000;
const WAIT = 5 * 60_000;

export type CorrectedLines = components['schemas']['CorrectedLines'];
type Correction = { transaction_id: string; reason: string; lines?: CorrectedLines };

/** A requisition's live entry reversed, or corrected when there are lines: the run started, then watched until it
 * ends. Done is the page as it is after; anything else is why not. Its toasts are the mutation's, not the button's:
 * the button goes once the entry isn't live, which is before the run ends, and a component's own callbacks go with it */
export function useCorrection(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ transaction_id, reason, lines }: Correction) => {
      const { run } = await unwrap(
        lines
          ? api.POST('/api/forms/requisition/submissions/{id}/correct', {
              params: { path: { id } },
              body: { transaction_id, reason, lines },
            })
          : api.POST('/api/forms/requisition/submissions/{id}/reverse', {
              params: { path: { id } },
              body: { transaction_id, reason },
            }),
      );
      const not = lines ? 'Not corrected' : 'Not reversed';
      const until = Date.now() + WAIT;
      while (Date.now() < until) {
        await new Promise((r) => setTimeout(r, EVERY));
        const s = await queryClient.query({ ...submissionQueries.one('requisition', id), staleTime: 0 });
        const ended = s.runs.find((r) => r.id === run && r.completed_at);
        if (!ended) continue;
        // The run ends as what the requisition now is, not done
        if (ended.status !== (lines ? 'corrected' : 'reversed'))
          throw new ApiError(0, `${not}: ${ended.reason ?? ended.status ?? 'it failed'}`);
        return s;
      }
      throw new ApiError(0, `Still ${lines ? 'correcting' : 'reversing'}: check back in a few minutes`);
    },
    onMutate: ({ transaction_id, lines }) => ({
      waiting: toast.loading(`${lines ? 'Correcting' : 'Reversing'} transaction ${transaction_id}…`),
    }),
    onSuccess: (_, { transaction_id, lines }, context) => {
      toast.success(`Transaction ${transaction_id} ${lines ? 'corrected' : 'reversed'}`, { id: context.waiting });
    },
    // Why not is the error's own toast
    onError: (_, __, context) => {
      if (context) toast.dismiss(context.waiting);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['submissions', 'requisition'] });
      void queryClient.invalidateQueries({ queryKey: ['journal_entries'] });
      void queryClient.invalidateQueries({ queryKey: ['journal_entry'] });
    },
  });
}

// What a correction's lines can post to, in the entry's tenant: read when the dialog opens, and kept a while
export const useAccounts = (tenant: string | null | undefined, enabled: boolean) =>
  useQuery({
    queryKey: ['accounts', tenant ?? null],
    queryFn: () => unwrap(api.GET('/api/accounts', { params: { query: { tenant } } })),
    enabled,
    staleTime: 10 * 60_000,
  });
