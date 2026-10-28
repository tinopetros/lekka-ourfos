import { render, screen } from '@testing-library/react';
import { FileDialog } from './FileDialog';

const FILE = { name: 'File 1', drive_id: null, ref: 'gs://b/vehicle_log/v1/d4279e8e.png' };

test('a file opens over the page when a link asks for it', () => {
  render(<FileDialog file={FILE} open />);
  expect(screen.getByRole('dialog')).toHaveTextContent('From our attachments');
});

test('otherwise it waits to be opened', () => {
  render(<FileDialog file={FILE} />);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
