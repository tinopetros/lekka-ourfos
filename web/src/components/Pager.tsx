import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePages } from '@/lib/usePages';

export function Pager({ next, fetching }: { next: string | null; fetching: boolean }) {
  const { page, older, newer } = usePages();
  return (
    <div className="flex items-center justify-end gap-2 pt-3 text-sm text-muted-foreground">
      <span>Page {page}</span>
      <Button variant="outline" size="sm" disabled={page === 1 || fetching} onClick={newer}>
        <ChevronLeft /> Newer
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={!next || fetching}
        onClick={() => {
          if (next) older(next);
        }}
      >
        Older <ChevronRight />
      </Button>
    </div>
  );
}
