import { useMatch } from 'react-router';

// On a record's own page, where the sidebar gets out of the way
export function useOnRecord(): boolean {
  const submission = useMatch('/forms/:form/:id');
  const entry = useMatch('/journal/:id');
  return Boolean(submission ?? entry);
}
