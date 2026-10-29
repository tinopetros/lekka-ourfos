import type { ReactNode } from 'react';
import { TabsList, TabsTrigger } from '@/components/ui/tabs';

// Boxed when open, its bottom edge the page's colour, so it joins what's below. Important, to win over the line
// variant's dark mode; its underline off
const TAB =
  '-mb-px h-auto flex-none rounded-b-none rounded-t-md border px-4 py-1.5 after:hidden data-active:border-border! data-active:border-b-background! data-active:text-foreground focus-visible:ring-0 focus-visible:outline-none';

// A line across the page, the open tab a box sitting on it, open at the bottom: everything below is that tab's
export function RecordTabs({ children }: { children: ReactNode }) {
  return (
    <div className="border-b">
      <TabsList variant="line" className="gap-0 p-0 group-data-horizontal/tabs:h-auto">
        {children}
      </TabsList>
    </div>
  );
}

export function RecordTab({ value, children }: { value: string; children: ReactNode }) {
  return (
    <TabsTrigger value={value} className={TAB}>
      {children}
    </TabsTrigger>
  );
}
