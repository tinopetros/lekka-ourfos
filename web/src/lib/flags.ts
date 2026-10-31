import { useBooleanFlagValue } from '@openfeature/react-sdk';
import { OpenFeature, TypedInMemoryProvider } from '@openfeature/web-sdk';

/** What's not for everyone yet. Each is off until someone who may switches it on, for themselves, in this browser:
 * kept here only, never in the database. OpenFeature, so a provider that serves them from elsewhere can take over */
export const FLAGS = {
  corrections: { key: 'enable-corrections', label: 'Enable corrections' },
  approvals: { key: 'enable-approvals', label: 'Enable approvals and comments' },
  testsInLists: { key: 'enable-tests-in-lists', label: 'Enable tests in lists' },
  testSubmissions: { key: 'enable-test-submissions', label: 'Enable test submissions' },
} as const;

export type Flag = keyof typeof FLAGS;

const STORE = 'ourfos.flags';

function stored(): Partial<Record<Flag, boolean>> {
  try {
    return JSON.parse(localStorage.getItem(STORE) ?? '{}') as Partial<Record<Flag, boolean>>;
  } catch {
    return {};
  }
}

function configuration(on: Partial<Record<Flag, boolean>>) {
  return Object.fromEntries(
    Object.entries(FLAGS).map(([name, { key }]) => [
      key,
      {
        variants: { on: true, off: false },
        defaultVariant: on[name as Flag] ? ('on' as const) : ('off' as const),
        disabled: false,
      },
    ]),
  );
}

const provider = new TypedInMemoryProvider(configuration(stored()));
void OpenFeature.setProvider(provider);

/** Whether it's on, here. Off until it's read */
export const useFlag = (flag: Flag) => useBooleanFlagValue(FLAGS[flag].key, false);

/** Switched on or off, for this browser only */
export function setFlag(flag: Flag, on: boolean) {
  const next = { ...stored(), [flag]: on };
  try {
    localStorage.setItem(STORE, JSON.stringify(next));
  } catch {
    // Kept for this visit only
  }
  void provider.putConfiguration(configuration(next));
}
