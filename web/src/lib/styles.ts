// A link looks like one, as on most sites: blue, underlined on hover
export const LINK = 'text-blue-600 underline-offset-2 hover:underline dark:text-blue-400';

// An action on a record's top row: outline, in its own color. Its dialog's confirm is the solid one
export const TONE = {
  success:
    'border-emerald-300 text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800 dark:border-emerald-800 dark:text-emerald-400 dark:hover:bg-emerald-950 dark:hover:text-emerald-300',
  danger:
    'border-red-300 text-red-700 hover:bg-red-50 hover:text-red-800 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950 dark:hover:text-red-300',
  neutral: '',
} as const;
