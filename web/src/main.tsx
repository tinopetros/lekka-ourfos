import '@/index.css';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { lazy, StrictMode, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router';
import { router } from '@/app/router';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ApiError } from '@/lib/api/client';

const queryClient = new QueryClient({
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
      <Suspense>
        <Devtools />
      </Suspense>
    </QueryClientProvider>
  </StrictMode>,
);
