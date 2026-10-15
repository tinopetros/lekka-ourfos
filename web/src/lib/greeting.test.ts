import { firstName } from './greeting';

test('a name is the start of an email until the directory gives us real ones', () => {
  expect(firstName('tpetros@lekkacredit.com')).toBe('Tpetros');
  expect(firstName('jane.doe@lekkacredit.com')).toBe('Jane');
});
