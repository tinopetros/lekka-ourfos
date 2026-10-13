import { render, screen } from '@testing-library/react';
import { ApiError } from '@/lib/api/client';
import { QueryState } from './QueryState';

test('an ended session asks you to sign in again', () => {
  render(<QueryState error={new ApiError(401, 'Your session has ended')} />);
  expect(screen.getByRole('button')).toHaveTextContent('Sign in again');
});

test('any other failure says why', () => {
  render(<QueryState error={new ApiError(404, 'No requisition r')} />);
  expect(screen.getByRole('alert')).toHaveTextContent('No requisition r');
});
