import { queryOptions, useQuery } from '@tanstack/react-query';
import { api, unwrap } from './client';

// What every page shares. A feature's own queries live in its api.ts
export const PAGE_SIZE = 25;

export const queries = {
  me: () => queryOptions({ queryKey: ['me'], queryFn: () => unwrap(api.GET('/api/me')), staleTime: Infinity }),
  forms: () => queryOptions({ queryKey: ['forms'], queryFn: () => unwrap(api.GET('/api/forms')), staleTime: Infinity }),
};

export const useMe = () => useQuery(queries.me());
export const useForms = () => useQuery(queries.forms());

/** Whether you may, e.g. `journal_entries:read`: the UI offers only what you may do, and the API checks either way */
export function useCan() {
  const { data: me } = useMe();
  return (permission: string) => me?.permissions.includes(permission) ?? false;
}

/** The forms whose submissions you may read */
export function useReadableForms() {
  const { data: forms = [] } = useForms();
  const can = useCan();
  return forms.filter((f) => can(`forms:${f.key}:read`));
}
