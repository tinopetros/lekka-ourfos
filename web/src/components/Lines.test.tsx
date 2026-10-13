import { render, screen } from '@testing-library/react';
import { Lines } from './Lines';

test('debits come before credits, each in its own column', () => {
  render(
    <Lines
      lines={[
        { name: 'Cash at Vault', glCode: '10000000', glId: 109, amount: 60, type: 'CREDIT' },
        { name: 'Fuel', glCode: '5040', glId: 70, amount: 60, type: 'DEBIT' },
      ]}
    />,
  );
  const rows = screen.getAllByRole('row').slice(1);
  expect(rows.map((r) => r.textContent)).toEqual(['Fuel 5040$60.00', 'Cash at Vault 10000000$60.00']);
});
