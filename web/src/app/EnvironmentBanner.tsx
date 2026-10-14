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
    <div role="status" className={cn('px-4 py-1 text-center text-xs font-semibold tracking-wide', tone)}>
      {banner}
    </div>
  );
}
