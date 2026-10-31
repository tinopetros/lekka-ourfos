import { Badge } from '@/components/ui/badge';

const TONES: Record<string, string> = {
  done: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200',
  approved: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200',
  disapproved: 'bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200',
  posted: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200',
  corrected: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200',
  live: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200',
  handed_over: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200',
  reversed: 'bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200',
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

// Said by a person on Ourfos, so shown whether or not ourfos tracks the form
const DECIDED = new Set(['approved', 'disapproved']);

/** A submission's status, where ourfos tracks it or someone decided it. Elsewhere only that it was received: the rest
 * is in its emails */
export function SubmissionStatus({ status, tracked }: { status: string | null; tracked: boolean }) {
  return tracked || DECIDED.has(status ?? '') ? (
    <StatusBadge status={status} />
  ) : (
    <Badge variant="secondary">received</Badge>
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
