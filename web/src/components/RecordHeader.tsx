import { ArrowLeft, ArrowRight, Share2 } from 'lucide-react';
import { useState } from 'react';
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
        <ShareLink />
        <Tip label={`Previous ${noun}`}>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label={`Previous ${noun}`}
            disabled={!neighbours.hasPrev}
            onClick={() => void neighbours.prev()}
          >
            <ArrowLeft />
          </Button>
        </Tip>
        <Tip label={`Next ${noun}`}>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label={`Next ${noun}`}
            disabled={!neighbours.hasNext}
            onClick={() => void neighbours.next()}
          >
            <ArrowRight />
          </Button>
        </Tip>
      </div>
    </div>
  );
}

// This record's own link, without where you came from, and a word beside it that it's copied
function ShareLink() {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative">
      <Tip label="Share link">
        <Button
          variant="outline"
          size="icon-sm"
          aria-label="Share link"
          onClick={() => {
            void navigator.clipboard.writeText(window.location.origin + window.location.pathname).then(() => {
              setCopied(true);
              setTimeout(() => {
                setCopied(false);
              }, 1500);
            });
          }}
        >
          <Share2 />
        </Button>
      </Tip>
      {copied && (
        <span
          role="status"
          className="absolute top-full right-0 z-50 mt-1 rounded-md border bg-muted px-2 py-1 text-xs whitespace-nowrap text-muted-foreground shadow-sm"
        >
          Link copied to clipboard
        </span>
      )}
    </div>
  );
}
