"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FeedCard } from "@/components/FeedCard";
import { FilterBar } from "@/components/FilterBar";
import { useSignalStore } from "@/lib/store";
import { BACKEND_URL } from "@/lib/api";
import type { FeedItem } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

const PAGE_SIZE = 20;

export default function DashboardPage() {
  const { t, locale } = useTranslation();
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);
  const pageRef = useRef(0);
  const [loadingMore, setLoadingMore] = useState(false);

  const {
    selectedCategory: category,
    setSelectedCategory: setCategory,
    urgencyFilter: urgency,
    setUrgencyFilter: setUrgency,
    searchQuery: search,
    setSearchQuery: setSearch,
    sortBy,
    setSortBy,
    lastUpdated,
    setLastUpdated,
    setCategoryCounts,
    setFeedCount,
  } = useSignalStore();

  const loadItems = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (urgency) params.set("urgency", urgency);
    if (search) params.set("q", search);
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", "0");
    if (sortBy) params.set("sort", sortBy);
    if (locale && locale !== "en") params.set("lang", locale);

    try {
      const res = await fetch(`${BACKEND_URL}/items?${params}`);
      const data = await res.json();
      const newItems: FeedItem[] = data.items || [];
      setItems(newItems);
      pageRef.current = 0;
      setTotalCount(data.count ?? data.total ?? newItems.length);
      setLastUpdated(new Date());
      setFeedCount(data.count ?? data.total ?? newItems.length);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [category, urgency, search, sortBy, locale, setLastUpdated, setFeedCount]);

  const loadMore = useCallback(async () => {
    setLoadingMore(true);
    const nextPage = pageRef.current + 1;
    const offset = nextPage * PAGE_SIZE;
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (urgency) params.set("urgency", urgency);
    if (search) params.set("q", search);
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    if (sortBy) params.set("sort", sortBy);
    if (locale && locale !== "en") params.set("lang", locale);

    try {
      const res = await fetch(`${BACKEND_URL}/items?${params}`);
      const data = await res.json();
      const newItems: FeedItem[] = data.items || [];
      setItems((prev) => [...prev, ...newItems]);
      pageRef.current = nextPage;
      setTotalCount(data.count ?? data.total ?? newItems.length);
    } catch {
      // ignore
    } finally {
      setLoadingMore(false);
    }
  }, [category, urgency, search, sortBy, locale]);

  // Load items on filter change
  useEffect(() => {
    loadItems();
    const interval = setInterval(loadItems, 30000);
    return () => clearInterval(interval);
  }, [loadItems]);

  // Compute category counts from current items
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    items.forEach((item) => {
      counts[item.category] = (counts[item.category] || 0) + 1;
    });
    return counts;
  }, [items]);

  useEffect(() => {
    setCategoryCounts(categoryCounts);
  }, [categoryCounts, setCategoryCounts]);

  // Debounce search
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const handleSearch = (v: string) => {
    setSearch(v);
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    searchTimeoutRef.current = setTimeout(() => loadItems(), 500);
  };

  const breakingCount = items.filter((i) => i.urgency === "breaking").length;
  const highCount = items.filter((i) => i.urgency === "high").length;
  const avgRelevance =
    items.length > 0
      ? (items.reduce((s, i) => s + i.relevance_score, 0) / items.length).toFixed(1)
      : "\u2014";

  const [secondsAgo, setSecondsAgo] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => {
      if (lastUpdated) {
        setSecondsAgo(Math.floor((Date.now() - lastUpdated.getTime()) / 1000));
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [lastUpdated]);

  const hasMore = items.length < totalCount;

  return (
    <>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">{t("feed.title")}</h2>
          <p className="text-sm text-slate-400 mt-1">
            {t("feed.subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">
            {t("common.updated")} {secondsAgo}{t("common.seconds")} {t("common.ago")}
          </span>
          <button
            onClick={loadItems}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
          >
            {t("common.refresh")}
          </button>
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
          <p className="text-2xl font-bold text-white">{totalCount}</p>
          <p className="text-xs text-slate-400">{t("common.totalItems")}</p>
        </div>
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
          <p className="text-2xl font-bold text-red-500">{breakingCount}</p>
          <p className="text-xs text-slate-400">{t("common.breaking")}</p>
        </div>
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
          <p className="text-2xl font-bold text-amber-500">{highCount}</p>
          <p className="text-xs text-slate-400">{t("common.highPriority")}</p>
        </div>
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
          <p className="text-2xl font-bold text-blue-400">{avgRelevance}</p>
          <p className="text-xs text-slate-400">{t("common.avgRelevance")}</p>
        </div>
      </div>

      {/* Category item counts */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {Object.entries(categoryCounts).map(([cat, count]) => (
          <span
            key={cat}
            className="px-2 py-1 rounded-lg text-xs bg-slate-800 text-slate-300"
          >
            {cat}: {count}
          </span>
        ))}
      </div>

      <FilterBar
        category={category}
        urgency={urgency}
        search={search}
        sortBy={sortBy}
        categoryCounts={categoryCounts}
        onCategoryChange={setCategory}
        onUrgencyChange={setUrgency}
        onSearchChange={handleSearch}
        onSortChange={(v) => setSortBy(v as "newest" | "relevance" | "urgency")}
      />

      {loading && items.length === 0 ? (
        <div className="text-center py-20 text-slate-500">
          <p className="text-lg">{t("feed.loadingFeed")}</p>
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-20 text-slate-500">
          <p className="text-lg mb-2">{t("feed.noItems")}</p>
          <p className="text-sm">
            {t("feed.noItemsDesc")}
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {items.map((item) => (
              <FeedCard key={item.id} item={item} showSource />
            ))}
          </div>

          {hasMore && (
            <div className="text-center mt-6">
              <button
                onClick={loadMore}
                disabled={loadingMore}
                className="px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {loadingMore
                  ? t("common.loading")
                  : `${t("feed.loadMore")} (${items.length} / ${totalCount})`}
              </button>
            </div>
          )}
        </>
      )}
    </>
  );
}
