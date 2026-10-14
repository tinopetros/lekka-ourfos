import { create } from 'zustand';

interface UiState {
  // The sidebar, on a phone, where it's a sheet
  menuOpen: boolean;
  setMenuOpen: (open: boolean) => void;
}

export const useUi = create<UiState>()((set) => ({
  menuOpen: false,
  setMenuOpen: (menuOpen) => {
    set({ menuOpen });
  },
}));
