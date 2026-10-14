import type { Me } from '@/lib/api/types';

/** Each environment's look, so nobody mistakes dev's data for the books. */
export const ENVIRONMENTS: Record<Me['environment'], { banner?: string; tone?: string; prefix?: string }> = {
  local: {
    banner: 'LOCAL: This is a local / dev environment, nothing here is really real',
    tone: 'bg-amber-500 text-black',
    prefix: '[LOCAL] ',
  },
  dev: {
    banner: 'TEST: This is a test environment, nothing here is really real',
    tone: 'bg-red-600 text-white',
    prefix: '[TEST] ',
  },
  prod: {},
};

/** The tab's title and icon say it too, so a tab or a screenshot can't be mistaken. */
export function markTab(environment: Me['environment']) {
  const { prefix = '' } = ENVIRONMENTS[environment];
  document.title = `${prefix}OurFOS`;
  if (environment !== 'prod') document.querySelector('link[rel=icon]')?.setAttribute('href', '/favicon-dev.svg');
}
