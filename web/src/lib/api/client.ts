import createClient from 'openapi-fetch';
import type { paths } from './schema';

export const api = createClient<paths>({ baseUrl: window.location.origin });

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
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
  throw new ApiError(response.status, typeof detail === 'string' ? detail : response.statusText || 'Request failed');
}
