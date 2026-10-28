import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { api } from '@/lib/api/client';
import { useSaveDraft } from './api';

afterEach(() => {
  vi.restoreAllMocks();
});

test("a saved draft is what's opened again, not what was cached before it", async () => {
  const client = new QueryClient();
  client.setQueryData(['submission', 'vehicle_log', 'd1'], { id: 'd1', status: 'draft', draft: { purpose: 'First' } });
  vi.spyOn(api, 'PUT').mockImplementation(() =>
    Promise.resolve({
      data: { id: 'd1', title: 'Second', updated_at: null, problems: [] },
      response: new Response(null, { status: 200 }),
    }),
  );
  vi.spyOn(api, 'GET').mockImplementation((() => new Promise(() => undefined)) as never);
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const { result } = renderHook(() => useSaveDraft('vehicle_log', 'd1'), { wrapper });
  act(() => {
    result.current.mutate({ values: { purpose: 'Second' }, answers: { purpose: 'Second' }, test: false });
  });
  await waitFor(() => {
    expect(client.getQueryData(['submission', 'vehicle_log', 'd1'])).toMatchObject({ draft: { purpose: 'Second' } });
  });
});
