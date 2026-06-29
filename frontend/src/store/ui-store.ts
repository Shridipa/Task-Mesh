import { create } from "zustand";

interface UiState {
  sidebarCollapsed: boolean;
  commandOpen: boolean;
  selectedJobId: string | null;
  setSidebarCollapsed: (value: boolean) => void;
  setCommandOpen: (value: boolean) => void;
  setSelectedJobId: (jobId: string | null) => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  commandOpen: false,
  selectedJobId: null,
  setSidebarCollapsed: (value) => set({ sidebarCollapsed: value }),
  setCommandOpen: (value) => set({ commandOpen: value }),
  setSelectedJobId: (jobId) => set({ selectedJobId: jobId })
}));
