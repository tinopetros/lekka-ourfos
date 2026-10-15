import { createBrowserRouter, Navigate } from 'react-router';
import { Root } from './Root';

// Every page, in one file. A record is a page of its own, so it's a link. Each page's code loads when it's first
// opened, so the first visit only fetches the shell and the page it's on
export const router = createBrowserRouter([
  {
    element: <Root />,
    children: [
      { index: true, lazy: async () => ({ Component: (await import('@/features/home/HomePage')).HomePage }) },
      {
        path: 'forms/:form',
        lazy: async () => ({ Component: (await import('@/features/submissions/SubmissionsPage')).SubmissionsPage }),
      },
      {
        path: 'forms/:form/:id',
        lazy: async () => ({ Component: (await import('@/features/submissions/SubmissionPage')).SubmissionPage }),
      },
      {
        path: 'journal',
        lazy: async () => ({ Component: (await import('@/features/journal/JournalPage')).JournalPage }),
      },
      {
        path: 'journal/:id',
        lazy: async () => ({ Component: (await import('@/features/journal/JournalEntryPage')).JournalEntryPage }),
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
