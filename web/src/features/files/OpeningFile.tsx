import { Loader2 } from 'lucide-react';
import { useEffect } from 'react';
import { useLocation } from 'react-router';

// A file of ours, opened in a new tab: this page shows until the file starts arriving, then the file takes its place.
// Replaced, not pushed, so Back skips it
export function OpeningFile() {
  const { pathname, search } = useLocation();
  useEffect(() => {
    document.title = 'Opening file…';
    window.location.replace(`/api${pathname}${search}`);
  }, [pathname, search]);
  return (
    <div className="flex h-svh items-center justify-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="size-4 animate-spin" /> Opening file…
    </div>
  );
}
