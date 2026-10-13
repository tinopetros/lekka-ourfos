import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { Line } from '@/lib/api/types';
import { money } from '@/lib/format';

/** A journal entry's lines, debits then credits, as an accountant reads them. */
export function Lines({ lines, currency }: { lines: Line[]; currency?: string | null }) {
  if (!lines.length) return null;
  const sorted = [...lines].sort((a, b) => (a.type === b.type ? 0 : a.type === 'DEBIT' ? -1 : 1));
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Account</TableHead>
          <TableHead className="text-right">Debit</TableHead>
          <TableHead className="text-right">Credit</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((l, i) => (
          <TableRow key={i}>
            <TableCell className="whitespace-normal">
              {l.name} <span className="text-muted-foreground">{l.glCode}</span>
            </TableCell>
            <TableCell className="text-right">{l.type === 'DEBIT' ? money(l.amount, currency ?? 'USD') : ''}</TableCell>
            <TableCell className="text-right">
              {l.type === 'CREDIT' ? money(l.amount, currency ?? 'USD') : ''}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
