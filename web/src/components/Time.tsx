import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { when } from '@/lib/format';

// Where the people who read these are, so nobody converts by hand
const ZONES = [
  ['Harare', 'Africa/Harare'],
  ['New York', 'America/New_York'],
  ['Los Angeles', 'America/Los_Angeles'],
  ['UTC', 'UTC'],
] as const;

// A time in the viewer's zone, dotted to say there's more: held over, it's the same time in each of ZONES
export function Time({ at }: { at: string | null | undefined }) {
  if (!at) return <>—</>;
  return (
    <HoverCard openDelay={700}>
      <HoverCardTrigger asChild>
        <time
          dateTime={at}
          tabIndex={0}
          className="cursor-help underline decoration-muted-foreground/50 decoration-dotted underline-offset-4"
        >
          {when(at)}
        </time>
      </HoverCardTrigger>
      <HoverCardContent align="start" className="w-auto text-sm">
        <dl className="grid grid-cols-[auto_auto] gap-x-3 gap-y-0.5">
          {ZONES.map(([name, zone]) => (
            <div key={zone} className="contents">
              <dt className="text-muted-foreground">{name}</dt>
              <dd>{when(at, zone)}</dd>
            </div>
          ))}
        </dl>
      </HoverCardContent>
    </HoverCard>
  );
}
