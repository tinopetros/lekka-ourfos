import { LoaderCircle } from 'lucide-react';
import type { ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { ApiError } from '@/lib/api/client';

/** Loading, or why not: one look for every query's wait and failure. */
export function QueryState({ error, children }: { error: Error | null; children?: ReactNode }) {
  if (!error)
    return (
      <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
        <LoaderCircle className="size-4 animate-spin" /> {children ?? 'Loading…'}
      </div>
    );
  const signedOut = error instanceof ApiError && error.status === 401;
  return (
    <div role="alert" className="flex flex-col items-start gap-3 p-6 text-sm">
      <p className="text-destructive">{signedOut ? 'Your session has ended.' : error.message}</p>
      <Button
        size="sm"
        variant="outline"
        onClick={() => {
          window.location.reload();
        }}
      >
        {signedOut ? 'Sign in again' : 'Reload'}
      </Button>
    </div>
  );
}
