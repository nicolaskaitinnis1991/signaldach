"use client";

import { clsx } from "clsx";
import { useTranslation } from "@/lib/i18n";

interface FilterBarProps {
  category: string;
  urgency: string;
  search: string;
  sortBy: string;
  categoryCounts?: Record<string, number>;
  onCategoryChange: (v: string) => void;
  onUrgencyChange: (v: string) => void;
  onSearchChange: (v: string) => void;
  onSortChange: (v: string) => void;
}

export function FilterBar({
  category,
  urgency,
  search,
  sortBy,
  categoryCounts,
  onCategoryChange,
  onUrgencyChange,
  onSearchChange,
  onSortChange,
}: FilterBarProps) {
  const { t } = useTranslation();

  const CATEGORIES = [
    { value: "", label: t("common.all") },
    { value: "regulation", label: t("feed.regulation") },
    { value: "competition", label: t("feed.competition") },
    { value: "market", label: t("feed.market") },
    { value: "sentiment", label: t("feed.sentiment") },
  ];

  const URGENCIES = [
    { value: "", label: t("feed.allUrgency") },
    { value: "breaking", label: t("common.breaking") },
    { value: "high", label: t("feed.high") },
    { value: "normal", label: t("feed.normal") },
  ];

  const SORT_OPTIONS = [
    { value: "newest", label: t("feed.newest") },
    { value: "relevance", label: t("feed.relevance") },
    { value: "urgency", label: t("feed.urgency") },
  ];

  return (
    <div className="flex flex-wrap items-center gap-3 mb-6">
      {/* Category pills */}
      <div className="flex gap-1">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.value}
            onClick={() => onCategoryChange(cat.value)}
            className={clsx(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
              category === cat.value
                ? "bg-blue-600 text-white"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            )}
          >
            {cat.label}
            {categoryCounts && cat.value && categoryCounts[cat.value] !== undefined && (
              <span className="ml-1 opacity-70">({categoryCounts[cat.value]})</span>
            )}
          </button>
        ))}
      </div>

      {/* Urgency select */}
      <select
        value={urgency}
        onChange={(e) => onUrgencyChange(e.target.value)}
        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 border-0 text-slate-300"
      >
        {URGENCIES.map((u) => (
          <option key={u.value} value={u.value}>
            {u.label}
          </option>
        ))}
      </select>

      {/* Sort */}
      <select
        value={sortBy}
        onChange={(e) => onSortChange(e.target.value)}
        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 border-0 text-slate-300"
      >
        {SORT_OPTIONS.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>

      {/* Search */}
      <div className="flex-1 min-w-[200px]">
        <input
          type="text"
          placeholder={t("feed.searchPlaceholder")}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full px-4 py-1.5 rounded-lg text-xs bg-slate-800 border-0 text-slate-200 placeholder:text-slate-500 focus:ring-2 focus:ring-blue-500 focus:outline-none"
        />
      </div>
    </div>
  );
}
