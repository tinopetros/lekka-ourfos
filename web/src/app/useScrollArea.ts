import { useLayoutEffect, useRef } from 'react';
import { NavigationType, useLocation, useNavigationType } from 'react-router';

/** A navigation that's the same page under another URL, like a new form becoming its draft's: it keeps its scroll */
export interface KeepScroll {
  keepScroll: true;
}

/** Where the page scrolls, as the router would the window's: a new page starts at its top, and Back finds you where
 * you were. The router's own restores the window's scroll alone, and ours is the scroll area beside the sidebar */
export function useScrollArea() {
  const area = useRef<HTMLElement>(null);
  const location = useLocation();
  const key = location.key;
  const keep = (location.state as Partial<KeepScroll> | null)?.keepScroll === true;
  const type = useNavigationType();
  const positions = useRef(new Map<string, number>());

  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    if (type === NavigationType.Pop) el.scrollTop = positions.current.get(key) ?? 0;
    else if (!keep) el.scrollTop = 0;
    const remember = () => {
      positions.current.set(key, el.scrollTop);
    };
    remember();
    el.addEventListener('scroll', remember, { passive: true });
    return () => {
      el.removeEventListener('scroll', remember);
    };
  }, [key, type, keep]);

  return area;
}
