import { useEffect } from 'react';
import { cn } from '@/lib/utils';
import type { Me } from '@/lib/api/types';
import { ENVIRONMENTS, markTab } from './environment';

export function EnvironmentBanner({ environment }: { environment: Me['environment'] }) {
  useEffect(() => {
    markTab(environment);
  }, [environment]);
  const { banner, tone } = ENVIRONMENTS[environment];
  if (!banner) return null;
  return (
    <div
      role="status"
      className={cn('h-6 shrink-0 truncate px-4 text-center text-xs leading-6 font-semibold tracking-wide', tone)}
    >
      {banner}
    </div>
  );
}
