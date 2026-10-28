import createClient from 'openapi-fetch';
import type { paths } from './schema';

export const api = createClient<paths>({ baseUrl: window.location.origin });

// What the API found wrong with what was sent, each by where it is: a field's name, or nothing for the whole of it
export interface Problem {
  loc: (string | number)[];
  msg: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly problems: Problem[];

  constructor(status: number, message: string, problems: Problem[] = []) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.problems = problems;
  }
}

export async function unwrap<T>(call: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  let result: Awaited<typeof call>;
  try {
    result = await call;
  } catch {
    // IAP answers an expired session with a redirect to Google's sign-in, which fetch can't follow across origins
    throw new ApiError(401, 'Your session has ended');
  }
  const { data, error, response } = result;
  if (response.ok && data !== undefined) return data;
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (Array.isArray(detail)) throw new ApiError(response.status, 'Some answers need another look', detail as Problem[]);
  throw new ApiError(response.status, typeof detail === 'string' ? detail : response.statusText || 'Request failed');
}
