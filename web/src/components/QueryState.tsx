import type { ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { ApiError } from '@/lib/api/client';

// While loading, whatever skeleton the page passes; failed, why, and a way to try again
export function QueryState({ error, loading }: { error: Error | null; loading?: ReactNode }) {
  if (!error) return <>{loading}</>;
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
