"use client";

import { useCallback, useEffect, useState } from "react";
import { clsx } from "clsx";
import { BACKEND_URL, stripHtml, timeAgo, type FeedItem } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

// Jurisdiction detection and colors
const JURISDICTIONS = {
  DE: {
    labelKey: "regulatory.germany",
    keywords: ["bafin", "bundestag", "deutschland", "german", "germany"],
    colors: "bg-yellow-900/50 text-yellow-300 border-yellow-700",
    accent: "#eab308",
  },
  CH: {
    labelKey: "regulatory.switzerland",
    keywords: ["finma", "schweiz", "swiss", "switzerland", "zurich", "geneva"],
    colors: "bg-red-900/50 text-red-300 border-red-700",
    accent: "#dc2626",
  },
  EU: {
    labelKey: "regulatory.eu",
    keywords: ["esma", "mica", "eu", "european", "brussels", "dora"],
    colors: "bg-blue-900/50 text-blue-300 border-blue-700",
    accent: "#2563eb",
  },
} as const;

type JurisdictionKey = keyof typeof JURISDICTIONS;

function detectJurisdiction(item: FeedItem): JurisdictionKey | null {
  const text = `${item.title} ${item.summary || ""} ${item.source_name || ""}`.toLowerCase();
  for (const [key, config] of Object.entries(JURISDICTIONS)) {
    if (config.keywords.some((kw) => text.includes(kw))) {
      return key as JurisdictionKey;
    }
  }
  return null;
}

export default function RegulatoryPage() {
  const { t, locale } = useTranslation();
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<JurisdictionKey | "all">("all");
  const [viewMode, setViewMode] = useState<"list" | "timeline">("list");

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const lp = locale && locale !== "en" ? `&lang=${locale}` : "";
      const res = await fetch(
        `${BACKEND_URL}/items?category=regulation&limit=100&sort=newest${lp}`
      );
      const data = await res.json();
      setItems(data.items || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [locale]);

  useEffect(() => {
    loadItems();
    const interval = setInterval(loadItems, 60000);
    return () => clearInterval(interval);
  }, [loadItems]);

  // Group items by jurisdiction
  const grouped: Record<JurisdictionKey | "other", FeedItem[]> = {
    DE: [],
    CH: [],
    EU: [],
    other: [],
  };

  items.forEach((item) => {
    const j = detectJurisdiction(item);
    if (j) grouped[j].push(item);
    else grouped.other.push(item);
  });

  const filteredItems =
    filter === "all"
      ? items
      : filter in grouped
        ? grouped[filter as JurisdictionKey]
        : items;

  // Group by month for timeline
  const byMonth: Record<string, FeedItem[]> = {};
  filteredItems.forEach((item) => {
    const date = item.published_at
      ? new Date(item.published_at)
      : new Date(item.created_at);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    if (!byMonth[key]) byMonth[key] = [];
    byMonth[key].push(item);
  });

  return (
    <>
      <div className="mb-8 flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white">
            {t("regulatory.title")}
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            {t("regulatory.subtitle")}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setViewMode("list")}
            className={clsx(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
              viewMode === "list"
                ? "bg-blue-600 text-white"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            )}
          >
            {t("regulatory.list")}
          </button>
          <button
            onClick={() => setViewMode("timeline")}
            className={clsx(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
              viewMode === "timeline"
                ? "bg-blue-600 text-white"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            )}
          >
            {t("regulatory.timeline")}
          </button>
        </div>
      </div>

      {/* Jurisdiction filter */}
      <div className="flex gap-2 mb-6 flex-wrap">
        <button
          onClick={() => setFilter("all")}
          className={clsx(
            "px-4 py-2 rounded-lg text-xs font-semibold transition-colors",
            filter === "all"
              ? "bg-slate-700 text-white"
              : "bg-slate-800 text-slate-300 hover:bg-slate-700"
          )}
        >
          {t("regulatory.allFilter")} ({items.length})
        </button>
        {(Object.entries(JURISDICTIONS) as [JurisdictionKey, (typeof JURISDICTIONS)[JurisdictionKey]][]).map(
          ([key, config]) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={clsx(
                "px-4 py-2 rounded-lg text-xs font-semibold transition-colors border",
                filter === key ? config.colors : "bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800"
              )}
            >
              {key === "DE" && "\uD83C\uDDE9\uD83C\uDDEA"}{" "}
              {key === "CH" && "\uD83C\uDDE8\uD83C\uDDED"}{" "}
              {key === "EU" && "\uD83C\uDDEA\uD83C\uDDFA"}{" "}
              {t(config.labelKey)} ({grouped[key].length})
            </button>
          )
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="bg-slate-900 rounded-xl border-2 border-yellow-700 p-4">
          <p className="text-2xl font-bold text-white">{grouped.DE.length}</p>
          <p className="text-xs text-slate-400">BaFin / DE</p>
        </div>
        <div className="bg-slate-900 rounded-xl border-2 border-red-700 p-4">
          <p className="text-2xl font-bold text-white">{grouped.CH.length}</p>
          <p className="text-xs text-slate-400">FINMA / CH</p>
        </div>
        <div className="bg-slate-900 rounded-xl border-2 border-blue-700 p-4">
          <p className="text-2xl font-bold text-white">{grouped.EU.length}</p>
          <p className="text-xs text-slate-400">ESMA / EU</p>
        </div>
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
          <p className="text-2xl font-bold text-white">{grouped.other.length}</p>
          <p className="text-xs text-slate-400">{t("regulatory.other")}</p>
        </div>
      </div>

      {loading ? (
        <p className="text-slate-500 text-center py-20">
          {t("regulatory.loadingRegulatory")}
        </p>
      ) : filteredItems.length === 0 ? (
        <div className="text-center py-20 text-slate-500">
          <p className="text-lg mb-2">{t("regulatory.noItems")}</p>
          <p className="text-sm">
            {t("regulatory.noItemsDesc")}
          </p>
        </div>
      ) : viewMode === "list" ? (
        <div className="space-y-3">
          {filteredItems.map((item) => {
            const jurisdiction = detectJurisdiction(item);
            const jConfig = jurisdiction ? JURISDICTIONS[jurisdiction] : null;

            return (
              <a
                key={item.id}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className={clsx(
                  "block bg-slate-900 rounded-xl border p-5 hover:border-slate-600 transition-all duration-200",
                  jConfig ? `border-l-4` : "border-slate-700",
                  jurisdiction === "DE" && "border-l-yellow-500",
                  jurisdiction === "CH" && "border-l-red-500",
                  jurisdiction === "EU" && "border-l-blue-500"
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      {jurisdiction && (
                        <span
                          className={clsx(
                            "px-2 py-0.5 rounded-full text-[10px] font-bold border",
                            jConfig?.colors
                          )}
                        >
                          {jurisdiction}
                        </span>
                      )}
                      {item.urgency !== "normal" && (
                        <span
                          className={clsx(
                            "px-2 py-0.5 rounded-full text-[10px] font-bold",
                            item.urgency === "breaking"
                              ? "bg-red-500 text-white"
                              : "bg-amber-500 text-amber-950"
                          )}
                        >
                          {item.urgency.toUpperCase()}
                        </span>
                      )}
                      {item.source_name && (
                        <span className="text-[10px] text-slate-500">
                          {item.source_name}
                        </span>
                      )}
                      <span className="text-[10px] text-slate-500">
                        {timeAgo(item.published_at)}
                      </span>
                    </div>
                    <h3 className="font-semibold text-white text-sm leading-snug mb-1">
                      {item.title}
                    </h3>
                    {item.summary && (
                      <p className="text-xs text-slate-400 line-clamp-2">
                        {stripHtml(item.summary)}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col items-center gap-1 flex-shrink-0">
                    <div
                      className={clsx(
                        "w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold",
                        item.relevance_score >= 8
                          ? "bg-red-950/50 text-red-400"
                          : item.relevance_score >= 5
                            ? "bg-amber-950/50 text-amber-400"
                            : "bg-slate-800 text-slate-500"
                      )}
                    >
                      {item.relevance_score}
                    </div>
                  </div>
                </div>
              </a>
            );
          })}
        </div>
      ) : (
        /* Timeline view */
        <div className="space-y-8">
          {Object.entries(byMonth)
            .sort(([a], [b]) => b.localeCompare(a))
            .map(([month, monthItems]) => (
              <div key={month}>
                <h3 className="text-sm font-bold text-slate-300 mb-4 sticky top-0 bg-slate-950 py-2">
                  {new Date(month + "-01").toLocaleDateString("en-US", {
                    month: "long",
                    year: "numeric",
                  })}
                  <span className="ml-2 text-xs font-normal text-slate-500">
                    ({monthItems.length} items)
                  </span>
                </h3>
                <div className="relative ml-6">
                  <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-slate-700" />
                  <div className="space-y-4">
                    {monthItems.map((item) => {
                      const jurisdiction = detectJurisdiction(item);
                      return (
                        <div key={item.id} className="flex gap-4">
                          <div className="relative flex-shrink-0 -ml-[5px]">
                            <div
                              className="w-3 h-3 rounded-full border-2 border-slate-900 shadow"
                              style={{
                                backgroundColor: jurisdiction
                                  ? JURISDICTIONS[jurisdiction].accent
                                  : "#94a3b8",
                              }}
                            />
                          </div>
                          <div className="flex-1 pb-2">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-[10px] text-slate-500">
                                {item.published_at
                                  ? new Date(item.published_at).toLocaleDateString(
                                      "de-DE"
                                    )
                                  : ""}
                              </span>
                              {jurisdiction && (
                                <span
                                  className={clsx(
                                    "px-1.5 py-0.5 rounded text-[10px] font-bold border",
                                    JURISDICTIONS[jurisdiction].colors
                                  )}
                                >
                                  {jurisdiction}
                                </span>
                              )}
                            </div>
                            <a
                              href={item.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm font-medium text-white hover:text-blue-400 transition-colors"
                            >
                              {item.title}
                            </a>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            ))}
        </div>
      )}
    </>
  );
}
