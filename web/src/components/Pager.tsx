import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useCan } from '@/lib/api/queries';
import { usePages } from '@/lib/usePages';

// Tests are left out of a list: whoever may make them can show them, at its foot as in the form
export function Pager({ next, fetching, tests }: { next: string | null; fetching: boolean; tests: string }) {
  const { page, older, newer, tests: showing, showTests } = usePages();
  const can = useCan();
  return (
    <div className="flex items-center justify-end gap-2 pt-3 text-sm text-muted-foreground">
      {can(tests) && (
        <div className="mr-auto flex items-center gap-2">
          <Switch id="tests" checked={showing} onCheckedChange={showTests} />
          <Label htmlFor="tests" className="font-normal">
            Show tests
          </Label>
        </div>
      )}
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
