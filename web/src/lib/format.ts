// A time in the viewer's own zone, named, so a screenshot can't be misread: 14 Oct 2026, 18:30 GMT+2
export function when(iso: string | null | undefined, timeZone?: string): string {
  if (!iso) return '—';
  const at = new Date(iso);
  return `${new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone }).format(at)} ${zone(at, timeZone)}`;
}

function zone(at: Date, timeZone?: string): string {
  return (
    new Intl.DateTimeFormat('en-GB', { timeZoneName: 'short', timeZone })
      .formatToParts(at)
      .find((p) => p.type === 'timeZoneName')?.value ?? ''
  );
}

const date = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeZone: 'UTC' });

// A date with no time, e.g. a transaction date: 2026-09-18 stays the 18th wherever you are
export function day(iso: string | null | undefined): string {
  return iso ? date.format(new Date(`${iso}T00:00:00Z`)) : '—';
}

export function money(amount: number | null | undefined, currency = 'USD'): string {
  if (amount === null || amount === undefined) return '—';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
}

// Name first, as Mifos lists them, and what's searched by most
export const accountLabel = (a: { glCode?: string | null; name: string }) => `${a.name} (${a.glCode})`;
