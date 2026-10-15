import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Link } from 'react-router';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import { Button } from '@/components/ui/button';
import { Tip } from './Tip';

// Back to the list, on the page you came from, and previous and next through it
export function RecordHeader({
  list,
  listPath,
  from,
  current,
  noun,
  neighbours,
}: {
  list: string;
  listPath: string;
  from: string;
  current: string;
  noun: string;
  neighbours: { prev: () => Promise<void>; next: () => Promise<void>; hasPrev: boolean; hasNext: boolean };
}) {
  return (
    <div className="mb-4 flex items-center gap-2">
      <Breadcrumb className="min-w-0">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to={{ pathname: listPath, search: from }}>{list}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem className="min-w-0">
            <BreadcrumbPage className="truncate">{current}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="ml-auto flex gap-1">
        <Tip label={`Previous ${noun} (←)`}>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label={`Previous ${noun}`}
            disabled={!neighbours.hasPrev}
            onClick={() => void neighbours.prev()}
          >
            <ChevronLeft />
          </Button>
        </Tip>
        <Tip label={`Next ${noun} (→)`}>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label={`Next ${noun}`}
            disabled={!neighbours.hasNext}
            onClick={() => void neighbours.next()}
          >
            <ChevronRight />
          </Button>
        </Tip>
      </div>
    </div>
  );
}
