import { createBrowserRouter, Navigate } from 'react-router';
import { HomePage } from '@/features/home/HomePage';
import { JournalEntryPage } from '@/features/journal/JournalEntryPage';
import { JournalPage } from '@/features/journal/JournalPage';
import { SubmissionPage } from '@/features/submissions/SubmissionPage';
import { SubmissionsPage } from '@/features/submissions/SubmissionsPage';
import { Root } from './Root';

// Every page, in one file. A record is a page of its own, so it's a link
export const router = createBrowserRouter([
  {
    element: <Root />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'forms/:form', element: <SubmissionsPage /> },
      { path: 'forms/:form/:id', element: <SubmissionPage /> },
      { path: 'journal', element: <JournalPage /> },
      { path: 'journal/:id', element: <JournalEntryPage /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
