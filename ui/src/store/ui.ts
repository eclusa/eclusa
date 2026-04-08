import { create } from 'zustand'

interface UIStore {
  selectedCascadeId: string | null
  openPanels: Set<string>
  authToken: string | null
  setSelectedCascade: (id: string | null) => void
  togglePanel: (panel: string) => void
  setAuthToken: (token: string | null) => void
}

export const useUIStore = create<UIStore>((set) => ({
  selectedCascadeId: null,
  openPanels: new Set<string>(),
  authToken: null,
  setSelectedCascade: (id) => set({ selectedCascadeId: id }),
  togglePanel: (panel) =>
    set((state) => {
      const next = new Set(state.openPanels)
      if (next.has(panel)) {
        next.delete(panel)
      } else {
        next.add(panel)
      }
      return { openPanels: next }
    }),
  setAuthToken: (token) => set({ authToken: token }),
}))
