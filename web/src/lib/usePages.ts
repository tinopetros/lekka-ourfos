import { useSearchParams } from 'react-router';

/** A list's page, in the URL so it can be shared and survives a reload: the cursors walked so far, oldest last, and
 * whether it shows tests. The one place a list reads or changes its search params. */
export function usePages() {
  const [params, setParams] = useSearchParams();
  const trail = params.get('after')?.split(',').filter(Boolean) ?? [];
  const tests = params.get('tests') === '1';

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
    tests,
    // Back to the first page: the cursors walked were through the other list
    showTests: (on: boolean) => {
      setParams(
        (p) => {
          p.delete('after');
          if (on) p.set('tests', '1');
          else p.delete('tests');
          return p;
        },
        { preventScrollReset: true },
      );
    },
    older: (next: string) => {
      go([...trail, next]);
    },
    newer: () => {
      go(trail.slice(0, -1));
    },
    search: params.toString(),
  };
}
