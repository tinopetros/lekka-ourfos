import { useSearchParams } from 'react-router';

/** A list's page, in the URL so it can be shared and survives a reload: the cursors walked so far, oldest last.
 * The one place a list reads or changes its search params (docs/phase13/adr.md 5). */
export function usePages() {
  const [params, setParams] = useSearchParams();
  const trail = params.get('after')?.split(',').filter(Boolean) ?? [];

  const go = (next: string[]) => {
    setParams(
      (p) => {
        if (next.length) p.set('after', next.join(','));
        else p.delete('after');
        return p;
      },
      { preventScrollReset: true },
    );
  };

  return {
    cursor: trail.at(-1),
    page: trail.length + 1,
    older: (next: string) => {
      go([...trail, next]);
    },
    newer: () => {
      go(trail.slice(0, -1));
    },
    search: params.toString(),
  };
}
