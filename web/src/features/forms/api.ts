import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, unwrap } from '@/lib/api/client';
import type { Values } from './schema';

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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['submissions', form] }),
  });
}
