import { Skeleton } from '@/components/ui/skeleton';

// Shaped like what's coming: a table's rows, a record's fields
export function TableSkeleton({ rows = 8, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <div className="space-y-3 rounded-md border p-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="flex gap-4">
          {Array.from({ length: columns }, (_, c) => (
            <Skeleton key={c} className={c === 1 ? 'h-4 flex-[2]' : 'h-4 flex-1'} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function RecordSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-6 w-64" />
      <Skeleton className="h-4 w-96 max-w-full" />
      <Skeleton className="h-8 w-48" />
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="flex gap-4">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-4 flex-1" />
        </div>
      ))}
    </div>
  );
}
