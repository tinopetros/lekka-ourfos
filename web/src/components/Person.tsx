import { Check, Copy } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { useName } from '@/lib/api/queries';

// Someone by their full name, dotted to say there's more: held over, their name and email, and a copy of the email
export function Person({ email }: { email: string | null | undefined }) {
  if (!email) return <>—</>;
  return <Named email={email} />;
}

function Named({ email }: { email: string }) {
  const name = useName(email);
  const [copied, setCopied] = useState(false);
  return (
    <HoverCard openDelay={700}>
      <HoverCardTrigger asChild>
        <span
          tabIndex={0}
          className="cursor-help underline decoration-muted-foreground/50 decoration-dotted underline-offset-4"
        >
          {name}
        </span>
      </HoverCardTrigger>
      <HoverCardContent align="start" className="w-auto max-w-sm text-sm">
        {name !== email && <div className="font-medium">{name}</div>}
        <div className="flex items-center gap-1 text-muted-foreground">
          <span className="truncate">{email}</span>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Copy email"
            onClick={() => {
              void navigator.clipboard.writeText(email).then(() => {
                setCopied(true);
                setTimeout(() => {
                  setCopied(false);
                }, 1500);
              });
            }}
          >
            {copied ? <Check /> : <Copy />}
          </Button>
        </div>
        {copied && <div className="text-xs text-muted-foreground">Email copied to clipboard</div>}
      </HoverCardContent>
    </HoverCard>
  );
}
