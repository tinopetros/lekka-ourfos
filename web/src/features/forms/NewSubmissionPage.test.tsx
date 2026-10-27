import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { api } from '@/lib/api/client';
import { NewSubmissionPage } from './NewSubmissionPage';

const ME = { email: 'ada@lekkacredit.com', environment: 'local', version: 'local' };
const FORMS = [{ key: 'vehicle_log', title: 'Vehicle logs', tracks_status: false }];

function open(permissions: string[], reply: (body: unknown) => Response) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  client.setQueryData(['me'], { ...ME, permissions });
  client.setQueryData(['forms'], FORMS);
  const sent: unknown[] = [];
  // openapi-fetch holds the fetch it was made with: the call itself is what's faked
  vi.spyOn(api, 'POST').mockImplementation((async (_path: string, init: { body: unknown }) => {
    sent.push(init.body);
    const response = reply(init.body);
    const json: unknown = await response.json();
    return response.ok ? { data: json, response } : { error: json, response };
  }) as never);
  const router = createMemoryRouter(
    [
      { path: '/forms/:form/new', element: <NewSubmissionPage /> },
      { path: '/forms/:form/:id', element: <p>The record</p> },
    ],
    { initialEntries: ['/forms/vehicle_log/new'] },
  );
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return sent;
}

const ok = () => new Response(JSON.stringify({ id: 'x', response_number: -1 }), { status: 200 });

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(new RegExp(`^${label}`)), { target: { value } });
}

afterEach(() => {
  vi.restoreAllMocks();
});

test("what's missing is said by its question, and nothing is sent", async () => {
  const sent = open(['forms:vehicle_log:submit'], ok);
  fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
  expect(await screen.findByText('Some answers need another look')).toBeInTheDocument();
  expect(screen.getAllByText('Required').length).toBeGreaterThan(0);
  expect(sent).toEqual([]);
});

test('a filled-in form is sent as typed answers, and becomes its record', async () => {
  const sent = open(['forms:vehicle_log:submit'], ok);
  fill('Purpose', 'Client visit');
  fill('Odometer at start', '100');
  fill('Odometer at end', '140');
  fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
  expect(await screen.findByText('The record')).toBeInTheDocument();
  expect(sent[0]).toMatchObject({
    answers: {
      vehicle: 'White Nissan Note | AGO8747',
      purpose: 'Client visit',
      odometer_start: 100,
      odometer_end: 140,
    },
    test: false,
  });
});

test('what only the API can check comes back by its question', async () => {
  open(['forms:vehicle_log:submit'], () =>
    Response.json({ detail: [{ loc: ['odometer_end'], msg: 'Below the start' }] }, { status: 422 }),
  );
  fill('Purpose', 'Client visit');
  fill('Odometer at start', '100');
  fill('Odometer at end', '140');
  fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
  await waitFor(() => {
    expect(screen.getAllByText('Below the start').length).toBeGreaterThan(0);
  });
});

test('a test is offered only to whoever may send one', () => {
  open(['forms:vehicle_log:submit'], ok);
  expect(screen.queryByRole('switch')).not.toBeInTheDocument();
});
