import { type QueryKey, useQuery, useQueryClient, type UseQueryOptions } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router';

interface Page<T> {
  items: T[];
  next: string | null;
}

// Where a record was opened from: its list's search params, so the way back lands on the same page of the list
export interface FromList {
  from?: string;
}

function trailOf(from: string): string[] {
  return new URLSearchParams(from).get('after')?.split(',').filter(Boolean) ?? [];
}

function searchOf(trail: string[], tests: boolean): string {
  return new URLSearchParams({
    ...(trail.length ? { after: trail.join(',') } : {}),
    ...(tests ? { tests: '1' } : {}),
  }).toString();
}

/** Previous and next through the list a record was opened from, into the neighbouring page when one runs out.
 * ← and → do the same, unless you're typing or something on the page took them. */
export function useNeighbours<T, K extends QueryKey>({
  id,
  list,
  idOf,
  pathOf,
}: {
  id: string;
  list: (cursor: string | undefined, tests: boolean) => UseQueryOptions<Page<T>, Error, Page<T>, K>;
  idOf: (item: T) => string;
  pathOf: (item: T) => string;
}) {
  const location = useLocation();
  const from = (location.state as FromList | null)?.from ?? '';
  const trail = trailOf(from);
  const tests = new URLSearchParams(from).get('tests') === '1';
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: page } = useQuery(list(trail.at(-1), tests));
  const items = page?.items ?? [];
  const i = items.findIndex((x) => idOf(x) === id);

  // The tab you're on comes too, so you can read the same tab from one record to the next
  const go = (item: T, at: string[]) => {
    void navigate(
      { pathname: pathOf(item), search: location.search },
      { state: { from: searchOf(at, tests) } satisfies FromList },
    );
  };
  const hasPrev = i > 0 || (i === 0 && trail.length > 0);
  const hasNext = i >= 0 && (i < items.length - 1 || Boolean(page?.next));

  const prev = async () => {
    const before = items[i - 1];
    if (i > 0 && before) {
      go(before, trail);
    } else if (i === 0 && trail.length) {
      const at = trail.slice(0, -1);
      const last = (await queryClient.query(list(at.at(-1), tests))).items.at(-1);
      if (last) go(last, at);
    }
  };
  const next = async () => {
    const after = items[i + 1];
    if (i >= 0 && after) {
      go(after, trail);
    } else if (i >= 0 && page?.next) {
      const first = (await queryClient.query(list(page.next, tests))).items[0];
      if (first) go(first, [...trail, page.next]);
    }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLElement && e.target.closest('input, textarea, select, [contenteditable]');
      // Taken already, e.g. by a row of tabs, whose arrows move between them
      if (typing || e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === 'ArrowLeft' && hasPrev) void prev();
      if (e.key === 'ArrowRight' && hasNext) void next();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
    };
  });

  return { prev, next, hasPrev, hasNext, from };
}
