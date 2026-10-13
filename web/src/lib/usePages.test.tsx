import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router';
import { usePages } from './usePages';

const at = (url: string) =>
  function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={[url]}>{children}</MemoryRouter>;
  };

test('older pages walk a trail of cursors in the URL, and newer walks back', () => {
  const { result } = renderHook(() => usePages(), { wrapper: at('/forms/requisition') });
  expect([result.current.page, result.current.cursor]).toEqual([1, undefined]);
  act(() => {
    result.current.older('a');
  });
  act(() => {
    result.current.older('b');
  });
  expect([result.current.page, result.current.cursor, result.current.search]).toEqual([3, 'b', 'after=a%2Cb']);
  act(() => {
    result.current.newer();
  });
  expect([result.current.page, result.current.cursor]).toEqual([2, 'a']);
});

test('a shared link opens on its page', () => {
  const { result } = renderHook(() => usePages(), { wrapper: at('/journal?after=x,y') });
  expect([result.current.page, result.current.cursor]).toEqual([3, 'y']);
});
