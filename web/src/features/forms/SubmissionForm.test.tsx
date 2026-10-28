import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { toast } from 'sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { api } from '@/lib/api/client';
import type { Submission } from '@/lib/api/types';
import { SubmissionPage } from '@/features/submissions/SubmissionPage';

const ME = { email: 'ada@lekkacredit.com', environment: 'local', version: 'local' };
const FORMS = [{ key: 'vehicle_log', title: 'Vehicle logs', tracks_status: false }];

const RECORD: Submission = {
  id: 'x',
  form: 'vehicle_log',
  response_number: -1,
  submitted_by: 'ada@lekkacredit.com',
  submitted_at: null,
  received_at: null,
  updated_at: null,
  status: 'received',
  test: false,
  title: 'The record',
  amount: null,
  live_entry: null,
  answers: [],
  raw: null,
  runs: [],
  journal_entries: [],
  draft: null,
};

function open(
  permissions: string[],
  reply: (body: unknown) => Response,
  at = '/forms/vehicle_log/new',
  record = RECORD,
  // What the API finds as a draft saves
  found: (body: unknown) => { loc: string[]; msg: string }[] = () => [],
) {
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
  // Saving the draft as it's filled in, and the record, once it's submitted
  const saves: unknown[] = [];
  vi.spyOn(api, 'PUT').mockImplementation((_path: string, init: { body: unknown }) => {
    saves.push(init.body);
    return Promise.resolve({
      data: { id: 'x', title: null, updated_at: null, problems: found(init.body) },
      response: new Response(null, { status: 200 }),
    });
  });
  vi.spyOn(api, 'GET').mockImplementation(((path: string) =>
    Promise.resolve({
      data: path.endsWith('/submissions') ? { items: [], next: null } : record,
      response: new Response(null, { status: 200 }),
    })) as never);
  const routes = [
    { path: '/forms/:form', element: <p>The list</p> },
    { path: '/forms/:form/:id', element: <SubmissionPage /> },
  ];
  const router = createMemoryRouter(routes, {
    initialEntries: [at],
  });
  render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
    </QueryClientProvider>,
  );
  return Object.assign(sent, { saves });
}

const ok = () => new Response(JSON.stringify({ id: 'x', response_number: -1 }), { status: 200 });

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(new RegExp(`^${label}`)), { target: { value } });
}

afterEach(() => {
  vi.restoreAllMocks();
});

test('leaving a question you changed saves the draft, and an untouched one saves nothing', async () => {
  const sent = open(['forms:vehicle_log:submit'], ok);
  const purpose = screen.getByLabelText(/^Purpose/);
  fireEvent.blur(purpose);
  fireEvent.change(purpose, { target: { value: 'Client visit' } });
  fireEvent.blur(purpose);
  await waitFor(() => {
    expect(sent.saves).toHaveLength(1);
  });
  expect(sent.saves[0]).toMatchObject({ values: { purpose: 'Client visit' }, test: false });
  fireEvent.blur(purpose);
  expect(sent.saves).toHaveLength(1);
  expect(await screen.findByText('Draft saved')).toBeInTheDocument();
});

test("what's missing is said by its question, and nothing is sent", async () => {
  const sent = open(['forms:vehicle_log:submit'], ok);
  fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
  expect(await screen.findByText('Some answers need another look')).toBeInTheDocument();
  expect(screen.getAllByText('Required').length).toBeGreaterThan(0);
  expect(sent).toHaveLength(0);
});

test('a filled-in form is sent as typed answers, and takes you back to the list', async () => {
  const sent = open(['forms:vehicle_log:submit'], ok);
  fill('Purpose', 'Client visit');
  fill('Odometer at start', '100');
  fill('Odometer at end', '140');
  fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
  expect(await screen.findByText('The list')).toBeInTheDocument();
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

test('a draft opened again, or reloaded, is its form with its answers', async () => {
  const draft = {
    ...RECORD,
    status: 'draft',
    response_number: null,
    draft: { purpose: 'Client visit', odometer_start: '100' },
  };
  open(['forms:vehicle_log:submit'], ok, '/forms/vehicle_log/d1', draft);
  expect(await screen.findByDisplayValue('Client visit')).toBeInTheDocument();
  expect(screen.getByDisplayValue('100')).toBeInTheDocument();
  expect(screen.getByText('Draft saved')).toBeInTheDocument();
});

test('Save draft saves what changed, and takes you back to the list', async () => {
  const sent = open(['forms:vehicle_log:submit'], ok);
  fireEvent.change(screen.getByLabelText(/^Purpose/), { target: { value: 'Client visit' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => {
    expect(sent.saves).toHaveLength(1);
  });
  expect(await screen.findByText('The list')).toBeInTheDocument();
});

test('a form you give up on asks first if you typed anything, and saves nothing', async () => {
  const sent = open(['forms:vehicle_log:submit'], ok);
  fireEvent.change(screen.getByLabelText(/^Purpose/), { target: { value: 'Client visit' } });
  fireEvent.click(screen.getByRole('button', { name: 'Discard' }));
  expect(await screen.findByText('Discard this vehicle log?')).toBeInTheDocument();
  expect(sent.saves).toHaveLength(0);
});

test('what the API finds as the draft saves shows on its question once you have been to it', async () => {
  open(['forms:vehicle_log:submit'], ok, '/forms/vehicle_log/new', RECORD, () => [
    { loc: ['odometer_end'], msg: 'Below the odometer at start' },
  ]);
  const end = screen.getByLabelText(/^Odometer at end/);
  fireEvent.focus(end);
  fireEvent.change(end, { target: { value: '1' } });
  fireEvent.blur(end);
  expect(await screen.findAllByText('Below the odometer at start')).not.toHaveLength(0);
});

test('an untouched form saves nothing, and says so', async () => {
  const sent = open(['forms:vehicle_log:submit'], ok);
  const said = vi.spyOn(toast, 'success');
  const plain = vi.spyOn(toast, 'message');
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
  expect(await screen.findByText('The list')).toBeInTheDocument();
  expect(sent.saves).toHaveLength(0);
  expect(said).not.toHaveBeenCalled();
  expect(plain).toHaveBeenCalledWith("Nothing to save: an empty vehicle log isn't kept");
});
