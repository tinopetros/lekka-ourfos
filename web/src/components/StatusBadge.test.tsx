import { render, screen } from '@testing-library/react';
import { SubmissionStatus } from './StatusBadge';

test('a tracked status is shown as it is', () => {
  render(<SubmissionStatus status="handed_over" tracked />);
  expect(screen.getByText('handed over')).toBeInTheDocument();
});

test('an untracked one only says it was received', () => {
  render(<SubmissionStatus status="handed_over" tracked={false} />);
  expect(screen.getByText('received')).toBeInTheDocument();
  expect(screen.queryByText('handed over')).not.toBeInTheDocument();
});
