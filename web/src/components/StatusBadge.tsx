import { Badge } from '@/components/ui/badge';

const TONES: Record<string, string> = {
  done: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200',
  posted: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200',
  live: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200',
  handed_over: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200',
  reversed: 'bg-slate-200 text-slate-800 dark:bg-slate-800 dark:text-slate-200',
  rejected: 'bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200',
  failed: 'bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200',
  refused: 'bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200',
};

/** A status as the store has it, handed_over read as "handed over". */
export function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-muted-foreground">—</span>;
  return (
    <Badge variant="secondary" className={TONES[status]}>
      {status.replaceAll('_', ' ')}
    </Badge>
  );
}

/** A test submission, in prod as anywhere: never a real one. */
export function TestBadge() {
  return (
    <Badge variant="outline" className="border-red-600 text-red-600">
      TEST
    </Badge>
  );
}
