const dateTime = new Intl.DateTimeFormat('en-GB', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'Africa/Harare',
});
const date = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeZone: 'UTC' });

/** In Harare's time, as the business is. */
export function when(iso: string | null | undefined): string {
  return iso ? dateTime.format(new Date(iso)) : '—';
}

/** A date with no time, e.g. a transaction date: 2026-09-18 stays the 18th wherever you are. */
export function day(iso: string | null | undefined): string {
  return iso ? date.format(new Date(`${iso}T00:00:00Z`)) : '—';
}

export function money(amount: number | null | undefined, currency = 'USD'): string {
  if (amount === null || amount === undefined) return '—';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
}
