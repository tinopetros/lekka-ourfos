import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, unwrap } from '@/lib/api/client';
import type { Values } from './schema';

export const draftQueries = {
  mine: (form: string) =>
    queryOptions({
      queryKey: ['drafts', form],
      queryFn: () => unwrap(api.GET('/api/forms/{form}/drafts', { params: { path: { form } } })),
    }),
};

export const useDrafts = (form: string, enabled: boolean) => useQuery({ ...draftQueries.mine(form), enabled });

/** Submits our own form's answers, under the id the page made for it: sending it twice is sending it once */
export function useSubmit(form: string, id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ answers, test }: { answers: Values; test: boolean }) =>
      unwrap(
        api.POST('/api/forms/{form}/submissions/{id}/submit', {
          params: { path: { form, id } },
          body: { answers, test },
        }),
      ),
    // Whatever was cached of it was a draft
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['submission', form, id] });
      void queryClient.invalidateQueries({ queryKey: ['submissions', form] });
      void queryClient.invalidateQueries({ queryKey: ['drafts', form] });
    },
  });
}

/** Saves a draft whole, as it's filled in. One draft's saves go one at a time, in order: a slow one is never
 * overtaken by a later one */
export function useSaveDraft(form: string, id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    scope: { id: `draft-${id}` },
    // values as typed, kept; answers as they'd be submitted, looked over: what's wrong comes back with the save
    mutationFn: ({ values, answers, test }: { values: Values; answers: Values; test: boolean }) =>
      unwrap(
        api.PUT('/api/forms/{form}/submissions/{id}', {
          params: { path: { form, id } },
          body: { values, answers, test },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['drafts', form] }),
  });
}

export function useDiscard(form: string, id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    scope: { id: `draft-${id}` },
    mutationFn: async () => {
      const { response } = await api.DELETE('/api/forms/{form}/submissions/{id}', { params: { path: { form, id } } });
      if (!response.ok) throw new ApiError(response.status, response.statusText || "Couldn't discard it");
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['submission', form, id] });
      void queryClient.invalidateQueries({ queryKey: ['drafts', form] });
    },
  });
}

/** A file for a draft, sent as it's picked: its gs:// ref, to keep in the draft */
export async function upload(form: string, id: string, file: File): Promise<string> {
  const url = `/api/forms/${form}/submissions/${id}/files?name=${encodeURIComponent(file.name)}`;
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
