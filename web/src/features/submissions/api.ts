import { keepPreviousData, queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, unwrap } from '@/lib/api/client';
import { toast } from 'sonner';
import { PAGE_SIZE, useCan } from '@/lib/api/queries';
import { useFlag } from '@/lib/flags';
import type { SubmissionSummary } from '@/lib/api/types';
import type { components } from '@/lib/api/schema';

export const submissionQueries = {
  list: (form: string, cursor?: string, tests = false) =>
    queryOptions({
      queryKey: ['submissions', form, cursor ?? null, tests],
      queryFn: () =>
        unwrap(
          api.GET('/api/forms/{form}/submissions', {
            params: { path: { form }, query: { cursor, limit: PAGE_SIZE, tests } },
          }),
        ),
    }),
  one: (form: string, id: string) =>
    queryOptions({
      queryKey: ['submission', form, id],
      queryFn: () => unwrap(api.GET('/api/forms/{form}/submissions/{id}', { params: { path: { form, id } } })),
    }),
};

// The page you were on stays while the next one loads
/** Whether a form's lists show tests: for whoever may make them, with Enable tests in lists on */
export function useTests(form: string) {
  const can = useCan();
  return useFlag('testsInLists') && can(`forms:${form}:test`);
}

export const useSubmissions = (form: string, cursor?: string, tests = false) =>
  useQuery({ ...submissionQueries.list(form, cursor, tests), placeholderData: keepPreviousData });

// The sheet opens at once with the row it was opened from, and fills in the rest when it comes. Off until there's
// one to fetch
export const useSubmission = (form: string, id: string, row?: SubmissionSummary, enabled = true) =>
  useQuery({
    ...submissionQueries.one(form, id),
    enabled,
    placeholderData: row && {
      ...row,
      answers: [],
      raw: null,
      runs: [],
      journal_entries: [],
      draft: null,
      actions: [],
      posting: null,
    },
  });

// How often, and how long, a correction's run is watched: a cold start and Mifos can take a minute or two
const EVERY = 2000;
const WAIT = 5 * 60_000;

export type CorrectedLines = components['schemas']['CorrectedLines'];
export type Filed = Omit<components['schemas']['PostRequest'], 'lines'>;
// A live entry reversed, or corrected with lines; or, with nothing live, lines posted where they're filed
type Correction =
  | { transaction_id: string; reason: string; lines?: CorrectedLines; post?: undefined }
  | { transaction_id?: undefined; reason?: undefined; lines: CorrectedLines; post: Filed };

// What each says as it runs, once it has, and how its run ends when it has: what the requisition now is
function said(c: Correction) {
  if (c.post) return { doing: 'Posting journal entry…', done: 'Journal entry posted', not: 'Not posted', ends: 'done' };
  if (c.lines)
    return {
      doing: `Correcting transaction ${c.transaction_id}…`,
      done: `Transaction ${c.transaction_id} corrected`,
      not: 'Not corrected',
      ends: 'corrected',
    };
  return {
    doing: `Reversing transaction ${c.transaction_id}…`,
    done: `Transaction ${c.transaction_id} reversed`,
    not: 'Not reversed',
    ends: 'reversed',
  };
}

/** A requisition's live entry reversed, or corrected when there are lines, or with nothing live, lines posted: the
 * run started, then watched until it ends. Done is the page as it is after; anything else is why not. Its toasts are
 * the mutation's, not the button's: the button goes once the entry isn't live, which is before the run ends, and a
 * component's own callbacks go with it */
export function useCorrection(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (c: Correction) => {
      const path = { params: { path: { id } } };
      const { run } = await unwrap(
        c.post
          ? api.POST('/api/forms/requisition/submissions/{id}/post', { ...path, body: { ...c.post, lines: c.lines } })
          : c.lines
            ? api.POST('/api/forms/requisition/submissions/{id}/correct', {
                ...path,
                body: { transaction_id: c.transaction_id, reason: c.reason, lines: c.lines },
              })
            : api.POST('/api/forms/requisition/submissions/{id}/reverse', {
                ...path,
                body: { transaction_id: c.transaction_id, reason: c.reason },
              }),
      );
      const { not, ends } = said(c);
      const until = Date.now() + WAIT;
      while (Date.now() < until) {
        await new Promise((r) => setTimeout(r, EVERY));
        const s = await queryClient.query({ ...submissionQueries.one('requisition', id), staleTime: 0 });
        const ended = s.runs.find((r) => r.id === run && r.completed_at);
        if (!ended) continue;
        if (ended.status !== ends) throw new ApiError(0, `${not}: ${ended.reason ?? ended.status ?? 'it failed'}`);
        return s;
      }
      throw new ApiError(0, `Still going: check back in a few minutes`);
    },
    onMutate: (c) => ({ waiting: toast.loading(said(c).doing) }),
    onSuccess: (_, c, context) => {
      toast.success(said(c).done, { id: context.waiting });
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
