import { ChevronsUpDown } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import type { components } from '@/lib/api/schema';
import { accountLabel as label } from '@/lib/format';
import { cn } from '@/lib/utils';

type Account = components['schemas']['Account'];

// Every word searched is in the account's name or GL code: cmdk's own fuzzy match finds "clean" in "Interest Receivable
// - Personal Loans"
const matches = (value: string, search: string, keywords: string[] = []) => {
  const text = [value, ...keywords].join(' ').toLowerCase();
  return search
    .toLowerCase()
    .split(/\s+/)
    .every((w) => text.includes(w))
    ? 1
    : 0;
};

// Picks one of the tenant's accounts. The search box opens empty, so the whole list is there to search, and only an
// account from it can be picked
export function AccountPicker({
  accounts,
  value,
  shown,
  loading,
  onPick,
}: {
  accounts: Account[];
  value?: number;
  // What the button reads when the line's account isn't one Mifos lets us post to
  shown?: string;
  loading: boolean;
  onPick: (a: Account) => void;
}) {
  const [open, setOpen] = useState(false);
  const picked = accounts.find((a) => a.glId === value);
  const groups = [
    { heading: 'Expenser’s accounts', items: accounts.filter((a) => a.expenser) },
    { heading: 'Other accounts', items: accounts.filter((a) => !a.expenser) },
  ].filter((g) => g.items.length);

  return (
    // Modal, so the list scrolls inside the dialog it opens from
    <Popover open={open} onOpenChange={setOpen} modal>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-label="Account"
          aria-expanded={open}
          aria-invalid={!picked && !loading}
          className="min-w-0 flex-1 justify-between font-normal"
        >
          <span className={cn('truncate', !picked && 'text-muted-foreground')}>
            {picked ? label(picked) : loading ? 'Loading accounts…' : (shown ?? 'Pick an account')}
          </span>
          <ChevronsUpDown className="opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) min-w-80 p-0" align="start">
        <Command filter={matches}>
          <CommandInput placeholder="Search by name or GL code" />
          <CommandList>
            <CommandEmpty>{loading ? 'Loading accounts…' : 'No account matches'}</CommandEmpty>
            {groups.map((g) => (
              <CommandGroup key={g.heading} heading={g.heading}>
                {g.items.map((a) => (
                  <CommandItem
                    key={a.glId}
                    value={label(a)}
                    keywords={[a.glCode]}
                    data-checked={a.glId === value}
                    onSelect={() => {
                      onPick(a);
                      setOpen(false);
                    }}
                  >
                    <span className="truncate">{a.name}</span>
                    <span className="text-muted-foreground tabular-nums">{a.glCode}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
