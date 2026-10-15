import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  // Generated, or shadcn's own, copied in as they come
  { ignores: ['dist', 'src/lib/api/schema.d.ts', 'src/components/ui/sidebar.tsx', 'src/hooks/use-mobile.ts'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.strictTypeChecked, reactHooks.configs.flat.recommended],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    plugins: { 'react-refresh': reactRefresh },
    rules: {
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/restrict-template-expressions': ['error', { allowNumber: true }],
    },
  },
  // shadcn's, copied in as they are, and the entry point, which renders rather than exports
  { files: ['src/components/ui/**', 'src/main.tsx'], rules: { 'react-refresh/only-export-components': 'off' } },
);
