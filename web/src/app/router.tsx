import { createBrowserRouter, Navigate } from 'react-router';
import { OpeningFile } from '@/features/files/OpeningFile';
import { Root } from './Root';

// Every page, in one file. A record is a page of its own, so it's a link. Each page's code loads when it's first
// opened, so the first visit only fetches the shell and the page it's on
export const router = createBrowserRouter([
  // Bare, without the sidebar, and not lazy: it's on screen only while a file is on its way
  { path: 'files/*', element: <OpeningFile /> },
  {
    element: <Root />,
    children: [
      { index: true, lazy: async () => ({ Component: (await import('@/features/home/HomePage')).HomePage }) },
      {
        path: 'forms/:form',
        lazy: async () => ({ Component: (await import('@/features/submissions/SubmissionsPage')).SubmissionsPage }),
      },
      // forms/:form/new too: a new one is the same page, its form, until it's submitted
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
