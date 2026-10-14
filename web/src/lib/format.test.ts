import { day, money, when } from './format';

test('a transaction date is the same day wherever you are', () => {
  expect(day('2026-09-18')).toBe('18 Sept 2026');
});

test("a time is the viewer's, its zone named", () => {
  expect(when('2026-10-13T22:30:00Z', 'Africa/Harare')).toBe('14 Oct 2026, 00:30 GMT+2');
  expect(when('2026-10-13T22:30:00Z', 'America/New_York')).toBe('13 Oct 2026, 18:30 GMT-4');
});

test('nothing is a dash, and money is dollars', () => {
  expect([day(null), when(undefined), money(null)]).toEqual(['—', '—', '—']);
  expect(money(1234.5)).toBe('$1,234.50');
});
