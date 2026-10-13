import createClient from 'openapi-fetch';
import type { paths } from './schema';

/** The API's own, typed from its OpenAPI: a path or a parameter it doesn't have fails to compile. Same origin, so
 * IAP's cookie goes with every call (docs/phase13/adr.md 7). */
export const api = createClient<paths>({ baseUrl: window.location.origin });

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** What a call answered, or an ApiError saying why not. FastAPI's errors say why in `detail`. */
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
