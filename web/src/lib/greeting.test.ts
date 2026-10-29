import { firstName } from './greeting';

test("a first name is Workspace's, or the start of an email without one", () => {
  expect(firstName('tpetros@lekkacredit.com', 'Tinotenda Petros')).toBe('Tinotenda');
  expect(firstName('tpetros@lekkacredit.com', null)).toBe('Tpetros');
  expect(firstName('jane.doe@lekkacredit.com')).toBe('Jane');
});
