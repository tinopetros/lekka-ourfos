import { queryOptions, useQuery } from '@tanstack/react-query';
import { api, unwrap } from './client';

// What every page shares. A feature's own queries live in its api.ts
export const PAGE_SIZE = 25;

export const queries = {
  me: () => queryOptions({ queryKey: ['me'], queryFn: () => unwrap(api.GET('/api/me')), staleTime: Infinity }),
  forms: () => queryOptions({ queryKey: ['forms'], queryFn: () => unwrap(api.GET('/api/forms')), staleTime: Infinity }),
  // A name changes rarely: one fetch a person a session, shared by every row they're on
  person: (email: string) =>
    queryOptions({
      queryKey: ['person', email],
      queryFn: () => unwrap(api.GET('/api/people/{email}', { params: { path: { email } } })),
      staleTime: Infinity,
    }),
};

export const useMe = () => useQuery(queries.me());
export const useForms = () => useQuery(queries.forms());

/** Someone's full name, or their email until it comes, or if the directory has none */
export function useName(email: string) {
  const { data } = useQuery(queries.person(email));
  return data?.name ?? email;
}

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
