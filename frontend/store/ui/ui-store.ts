import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Global UI/client state for the application shell. Only the sidebar collapse
 * preference is persisted; the mobile drawer is ephemeral. No server data.
 */
interface UiState {
  sidebarCollapsed: boolean;
  mobileNavOpen: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (value: boolean) => void;
  setMobileNavOpen: (value: boolean) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      mobileNavOpen: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (value) => set({ sidebarCollapsed: value }),
      setMobileNavOpen: (value) => set({ mobileNavOpen: value }),
    }),
    { name: "neuraevo.ui", partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed }) }
  )
);
