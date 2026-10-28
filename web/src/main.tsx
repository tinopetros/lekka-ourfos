import '@/index.css';
import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { lazy, StrictMode, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router';
import { router } from '@/app/router';
import { Toaster } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { toast } from 'sonner';
import { ApiError } from '@/lib/api/client';

const queryClient = new QueryClient({
  // An action that fails says so, wherever you are. Not what's wrong with a form's answers: it shows that by each field
  mutationCache: new MutationCache({
    onError: (error) => {
      if (error instanceof ApiError && error.problems.length > 0) return;
      toast.error(error.message);
    },
  }),
  defaultOptions: {
    queries: {
      // A list a minute old is fresh enough; coming back to the tab refetches it
      staleTime: 60_000,
      // Once more for a flaky connection, never for an answer: a 4xx won't change
      retry: (count, error) => count < 1 && !(error instanceof ApiError && error.status < 500),
    },
  },
});

// Only in `make web`: never in the build
const Devtools = import.meta.env.DEV
  ? lazy(() => import('@tanstack/react-query-devtools').then((m) => ({ default: m.ReactQueryDevtools })))
  : () => null;

const root = document.getElementById('root');
if (!root) throw new Error('No #root in index.html');

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={300}>
        <RouterProvider router={router} />
      </TooltipProvider>
      {/* Top right, below the header, so it covers neither the banner nor who you are; long enough to read and
          reach for its link, and closed any time */}
      <Toaster richColors position="top-right" offset={{ top: '4.5rem' }} duration={15_000} closeButton />
      <Suspense>
        <Devtools />
      </Suspense>
    </QueryClientProvider>
  </StrictMode>,
);
