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
