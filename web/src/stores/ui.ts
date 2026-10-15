import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

interface UiState {
  // The sidebar on lists and home, as you last left it
  expanded: boolean;
  // Kept open on a record's page too, once you've opened it there: it collapses there otherwise
  pinned: boolean;
  setSidebar: (open: boolean, onRecord: boolean) => void;
}

export const useUi = create<UiState>()(
  persist(
    (set) => ({
      expanded: true,
      pinned: false,
      setSidebar: (open, onRecord) => {
        set(onRecord ? { pinned: open } : { expanded: open });
      },
    }),
    // A private window or blocked storage leaves the defaults, every time
    { name: 'ourfos-ui', storage: createJSONStorage(() => localStorage) },
  ),
);
