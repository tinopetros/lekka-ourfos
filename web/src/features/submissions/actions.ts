import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api, ApiError, unwrap } from '@/lib/api/client';
import type { ActionKind } from '@/lib/api/types';

// How often, and how long, an action's run is asked how it went: a cold start and Mifos, for a reversal, take a while
const EVERY = 2000;
const WAIT = 5 * 60_000;

// What each says, as it runs, once it has, and when it hasn't
export const SAID: Record<ActionKind, { doing: string; done: string; not: string }> = {
  approve: { doing: 'Approving…', done: 'Approved', not: 'Not approved' },
  close: { doing: 'Closing…', done: 'Closed', not: 'Not closed' },
  comment: { doing: 'Commenting…', done: 'Comment sent', not: 'Comment not sent' },
};

/** A file for an action, sent before it's taken: its gs:// ref */
async function upload(form: string, id: string, file: File): Promise<string> {
  const url = `/api/forms/${form}/submissions/${id}/actions/files?name=${encodeURIComponent(file.name)}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      body: file,
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
    });
  } catch {
    throw new ApiError(0, `Couldn't send ${file.name}: check your connection`);
  }
  const body = (await response.json().catch(() => ({}))) as { ref?: string; detail?: unknown };
  if (!response.ok || !body.ref)
    throw new ApiError(response.status, typeof body.detail === 'string' ? body.detail : `Couldn't send ${file.name}`);
  return body.ref;
}

type Taken = { kind: ActionKind; comment: string; files: File[] };

/** An action taken: its files sent, its run started, then asked until it's kept or has failed. Done is once its
 * thread was told and it's on the record */
export function useAction(form: string, id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ kind, comment, files }: Taken) => {
      const refs = await Promise.all(files.map((f) => upload(form, id, f)));
      const { run } = await unwrap(
        api.POST('/api/forms/{form}/submissions/{id}/actions', {
          params: { path: { form, id } },
          body: { kind, comment, files: refs },
        }),
      );
      const until = Date.now() + WAIT;
      while (Date.now() < until) {
        await new Promise((r) => setTimeout(r, EVERY));
        const { state, reason } = await unwrap(
          api.GET('/api/forms/{form}/submissions/{id}/actions/{run}', { params: { path: { form, id, run } } }),
        );
        if (state === 'done') return;
        if (state === 'failed') throw new ApiError(0, `${SAID[kind].not}: ${reason ?? 'it failed'}`);
      }
      throw new ApiError(0, `Still going: check back in a few minutes`);
    },
    onMutate: ({ kind }) => ({ waiting: toast.loading(SAID[kind].doing) }),
    onSuccess: (_, { kind }, context) => {
      toast.success(SAID[kind].done, { id: context.waiting });
    },
    // Why not is the error's own toast
    onError: (_, __, context) => {
      if (context) toast.dismiss(context.waiting);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['submission', form, id] });
      void queryClient.invalidateQueries({ queryKey: ['submissions', form] });
      void queryClient.invalidateQueries({ queryKey: ['journal_entries'] });
    },
  });
}
