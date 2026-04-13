import { create } from "zustand";

interface SignalStore {
  // Filters
  selectedCategory: string;
  setSelectedCategory: (category: string) => void;
  urgencyFilter: string;
  setUrgencyFilter: (urgency: string) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  sortBy: "newest" | "relevance" | "urgency";
  setSortBy: (sort: "newest" | "relevance" | "urgency") => void;

  // Live status
  lastUpdated: Date | null;
  setLastUpdated: (date: Date) => void;
  isConnected: boolean;
  setIsConnected: (connected: boolean) => void;
  lastScrapeTime: string | null;
  setLastScrapeTime: (time: string | null) => void;

  // Counts for sidebar badges
  feedCount: number;
  setFeedCount: (count: number) => void;
  alertCount: number;
  setAlertCount: (count: number) => void;
  sourceCount: number;
  setSourceCount: (count: number) => void;
  breakingCount: number;
  setBreakingCount: (count: number) => void;

  // Category counts
  categoryCounts: Record<string, number>;
  setCategoryCounts: (counts: Record<string, number>) => void;
}

export const useSignalStore = create<SignalStore>((set) => ({
  selectedCategory: "",
  setSelectedCategory: (category) => set({ selectedCategory: category }),
  urgencyFilter: "",
  setUrgencyFilter: (urgency) => set({ urgencyFilter: urgency }),
  searchQuery: "",
  setSearchQuery: (query) => set({ searchQuery: query }),
  sortBy: "newest",
  setSortBy: (sort) => set({ sortBy: sort }),

  lastUpdated: null,
  setLastUpdated: (date) => set({ lastUpdated: date }),
  isConnected: false,
  setIsConnected: (connected) => set({ isConnected: connected }),
  lastScrapeTime: null,
  setLastScrapeTime: (time) => set({ lastScrapeTime: time }),

  feedCount: 0,
  setFeedCount: (count) => set({ feedCount: count }),
  alertCount: 0,
  setAlertCount: (count) => set({ alertCount: count }),
  sourceCount: 0,
  setSourceCount: (count) => set({ sourceCount: count }),
  breakingCount: 0,
  setBreakingCount: (count) => set({ breakingCount: count }),

  categoryCounts: {},
  setCategoryCounts: (counts) => set({ categoryCounts: counts }),
}));
