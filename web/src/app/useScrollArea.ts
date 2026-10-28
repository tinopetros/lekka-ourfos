import { useLayoutEffect, useRef } from 'react';
import { NavigationType, useLocation, useNavigationType } from 'react-router';

/** Where the page scrolls, as the router would the window's: a new page starts at its top, and Back finds you where
 * you were. The router's own restores the window's scroll alone, and ours is the scroll area beside the sidebar */
export function useScrollArea() {
  const area = useRef<HTMLElement>(null);
  const { key } = useLocation();
  const type = useNavigationType();
  const positions = useRef(new Map<string, number>());

  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    el.scrollTop = type === NavigationType.Pop ? (positions.current.get(key) ?? 0) : 0;
    const keep = () => {
      positions.current.set(key, el.scrollTop);
    };
    el.addEventListener('scroll', keep, { passive: true });
    return () => {
      el.removeEventListener('scroll', keep);
    };
  }, [key, type]);

  return area;
}
