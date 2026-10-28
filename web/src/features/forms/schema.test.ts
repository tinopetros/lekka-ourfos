import { blank, fields, message, padded, toAnswers, validator } from './schema';

test("a form's questions come in its order, each as its kind asks it", () => {
  const fs = fields('vehicle_log');
  expect(fs.map((f) => [f.key, f.kind, f.required])).toEqual([
    ['vehicle', 'choice', true],
    ['date', 'date', true],
    ['purpose', 'text', true],
    ['odometer_start', 'integer', true],
    ['odometer_end', 'integer', true],
    ['odometer_photos', 'files', false],
    ['vehicle_photos', 'files', false],
    ['comment', 'long', false],
  ]);
  expect(fs[2]?.description).toBe('Where to, and why');
});

test("a requisition's files are a group of their own, and a loan's folder has its picture", () => {
  const files = fields('requisition').find((f) => f.key === 'files');
  expect(files?.fields?.map((f) => f.title)).toEqual(['Signed requisition form', 'Receipts', 'Invoices']);
  expect(fields('loan_approval').find((f) => f.key === 'client_folder')).toMatchObject({
    kind: 'link',
    helpImage: 'client-folder.png',
  });
});

test('a trip starts today', () => {
  expect(blank(fields('vehicle_log')).date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
});

test("what's typed is sent as the API takes it: numbers as numbers, and empty answers left out", () => {
  const fs = fields('loan_approval');
  expect(toAnswers(fs, { applicant_first_name: ' Ada ', loan_amount: '1500.5', tenure: '6', purpose: '' })).toEqual({
    applicant_first_name: 'Ada',
    loan_amount: 1500.5,
    tenure: 6,
  });
});

test("what's wrong is said for whoever's filling it in", () => {
  const result = validator('requisition').safeParse({ amount: 12.345 }, { error: message });
  const issues = result.error?.issues.map((i) => [i.path.join('.'), i.message]);
  expect(issues).toEqual(
    expect.arrayContaining([
      ['payable_to', 'Required'],
      ['amount', 'To the cent: at most 2 decimal places'],
    ]),
  );
});

test("an account number is padded as Mifos has it, and what can't be is said plainly", () => {
  expect(padded('428')).toBe('000000428');
  expect(padded(' 000000428 ')).toBe('000000428');
  expect(padded('42a')).toBe('42a');
  const result = validator('write_off').safeParse({ loan_account_number: '42a' }, { error: message });
  const wrong = result.error?.issues.find((i) => i.path.join('.') === 'loan_account_number');
  expect(wrong?.message).toBe('Up to 9 digits, e.g. 428 or 000000428');
});
