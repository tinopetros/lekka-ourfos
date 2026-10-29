import { useLocation, useSearchParams } from 'react-router';

/** The record page's open tab, kept in the URL as ?tab=, so Back, a reload or a shared link opens on it. The first
 * of tabs when there's none, or one this record hasn't. Switching replaces the URL rather than adding to history, so
 * Back leaves the page, and keeps where in the list you came from */
export function useTab(tabs: string[]) {
  const [params, setParams] = useSearchParams();
  const state: unknown = useLocation().state;
  const asked = params.get('tab');
  const tab = asked && tabs.includes(asked) ? asked : (tabs[0] ?? '');
  const setTab = (next: string) => {
    setParams(
      (now) => {
        if (next === tabs[0]) now.delete('tab');
        else now.set('tab', next);
        return now;
      },
      { replace: true, state },
    );
  };
  return [tab, setTab] as const;
}
