import { createBrowserRouter, Navigate } from 'react-router';
import { JournalEntrySheet } from '@/features/journal/JournalEntrySheet';
import { JournalPage } from '@/features/journal/JournalPage';
import { SubmissionSheet } from '@/features/submissions/SubmissionSheet';
import { SubmissionsPage } from '@/features/submissions/SubmissionsPage';
import { Root } from './Root';

// Every route, in one file (docs/phase13/adr.md 5). A sheet is a child route, so an open one is a link
export const router = createBrowserRouter([
  {
    element: <Root />,
    children: [
      { index: true, element: <Navigate to="/forms/requisition" replace /> },
      {
        path: 'forms/:form',
        element: <SubmissionsPage />,
        children: [{ path: ':id', element: <SubmissionSheet /> }],
      },
      {
        path: 'journal',
        element: <JournalPage />,
        children: [{ path: ':id', element: <JournalEntrySheet /> }],
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
