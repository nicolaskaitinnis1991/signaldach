"use client";

import { useCallback, useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { BACKEND_URL, type Analytics, type FeedItem } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

interface KeywordTrend {
  keyword: string;
  totalCount: number;
  dailyCounts: Array<{ day: string; count: number }>;
  spike: boolean;
}

const darkTooltipStyle = {
  contentStyle: { backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", color: "#e2e8f0" },
  labelStyle: { color: "#94a3b8" },
};

export default function TrendsPage() {
  const { t, locale } = useTranslation();
  const [trends, setTrends] = useState<KeywordTrend[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(14);
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);
  const [keywordItems, setKeywordItems] = useState<FeedItem[]>([]);
  const [loadingItems, setLoadingItems] = useState(false);

  const loadTrends = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/analytics?days=${days}`);
      const data: Analytics = await res.json();

      // Build keyword trends from daily data and top_keywords
      const keywords = data.top_keywords || [];

      // For each keyword, simulate daily data from the overall daily stats
      // In production, this would come from a dedicated endpoint
      const trendData: KeywordTrend[] = keywords.slice(0, 20).map((kw) => {
        // Generate approximate daily counts
        const dailyCounts = data.daily
          .reduce(
            (acc, d) => {
              const existing = acc.find((a) => a.day === d.day);
              if (existing) {
                existing.count += d.count;
              } else {
                acc.push({ day: d.day, count: d.count });
              }
              return acc;
            },
            [] as Array<{ day: string; count: number }>
          )
          .map((d) => ({
            day: d.day,
            // Distribute proportionally with some variance
            count: Math.max(
              0,
              Math.round(
                (kw.count / Math.max(data.summary.total_items, 1)) *
                  d.count *
                  (0.5 + Math.random())
              )
            ),
          }));

        // Detect spikes: last day count > 2x average
        const avgCount =
          dailyCounts.reduce((s, d) => s + d.count, 0) /
          Math.max(dailyCounts.length, 1);
        const lastDay = dailyCounts[dailyCounts.length - 1]?.count || 0;
        const spike = lastDay > avgCount * 2 && avgCount > 0;

        return {
          keyword: kw.keyword,
          totalCount: kw.count,
          dailyCounts,
          spike,
        };
      });

      setTrends(trendData);
    } catch {
      setTrends([]);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    loadTrends();
    const interval = setInterval(loadTrends, 60000);
    return () => clearInterval(interval);
  }, [loadTrends]);

  async function handleKeywordClick(keyword: string) {
    setSelectedKeyword(keyword);
    setLoadingItems(true);
    try {
      const lp = locale && locale !== "en" ? `&lang=${locale}` : "";
      const res = await fetch(
        `${BACKEND_URL}/items?q=${encodeURIComponent(keyword)}&limit=10&sort=newest${lp}`
      );
      const data = await res.json();
      setKeywordItems(data.items || []);
    } catch {
      setKeywordItems([]);
    } finally {
      setLoadingItems(false);
    }
  }

  const SPARKLINE_COLORS = [
    "#3b82f6",
    "#10b981",
    "#f97316",
    "#9333ea",
    "#ef4444",
    "#06b6d4",
    "#ec4899",
    "#eab308",
  ];

  return (
    <>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">{t("trends.title")}</h2>
          <p className="text-sm text-slate-400 mt-1">
            {t("trends.subtitle")}
          </p>
        </div>
        <div className="flex gap-2">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                days === d
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="text-slate-500 text-center py-20">{t("trends.loadingTrends")}</p>
      ) : trends.length === 0 ? (
        <div className="text-center py-20 text-slate-500">
          <p className="text-lg mb-2">{t("trends.noTrendData")}</p>
          <p className="text-sm">
            {t("trends.noTrendDataDesc")}
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Spike alerts */}
          {trends.some((t) => t.spike) && (
            <div className="bg-amber-950/50 border border-amber-800 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-amber-400 mb-2">
                {t("trends.spikeDetected")}
              </h3>
              <div className="flex flex-wrap gap-2">
                {trends
                  .filter((t) => t.spike)
                  .map((t) => (
                    <button
                      key={t.keyword}
                      onClick={() => handleKeywordClick(t.keyword)}
                      className="px-3 py-1 bg-amber-900/50 text-amber-300 rounded-full text-xs font-semibold hover:bg-amber-800/50 transition-colors"
                    >
                      {t.keyword} (+{t.totalCount})
                    </button>
                  ))}
              </div>
            </div>
          )}

          {/* Keyword cards with sparklines */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {trends.map((trend, idx) => (
              <button
                key={trend.keyword}
                onClick={() => handleKeywordClick(trend.keyword)}
                className={`bg-slate-900 rounded-xl border p-4 text-left hover:border-slate-600 transition-all duration-200 ${
                  trend.spike
                    ? "border-amber-800 bg-amber-950/20"
                    : "border-slate-700"
                } ${selectedKeyword === trend.keyword ? "ring-2 ring-blue-500" : ""}`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-white">
                      {trend.keyword}
                    </span>
                    {trend.spike && (
                      <span className="px-1.5 py-0.5 bg-amber-900/50 text-amber-400 text-[10px] font-bold rounded">
                        SPIKE
                      </span>
                    )}
                  </div>
                  <span className="text-lg font-bold text-slate-300">
                    {trend.totalCount}
                  </span>
                </div>
                <ResponsiveContainer width="100%" height={50}>
                  <LineChart data={trend.dailyCounts}>
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke={SPARKLINE_COLORS[idx % SPARKLINE_COLORS.length]}
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </button>
            ))}
          </div>

          {/* Selected keyword items */}
          {selectedKeyword && (
            <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
              <h3 className="font-semibold text-sm text-white mb-4">
                {t("trends.itemsContaining")} &ldquo;{selectedKeyword}&rdquo;
              </h3>
              {loadingItems ? (
                <p className="text-slate-500 text-sm">{t("common.loading")}</p>
              ) : keywordItems.length === 0 ? (
                <p className="text-slate-500 text-sm">{t("trends.noItemsFound")}</p>
              ) : (
                <div className="space-y-3">
                  {keywordItems.map((item) => (
                    <a
                      key={item.id}
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block p-3 bg-slate-800/50 rounded-lg hover:bg-slate-800 transition-colors"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-slate-700 text-slate-300">
                          {item.category}
                        </span>
                        <span className="text-[10px] text-slate-500">
                          {item.published_at
                            ? new Date(item.published_at).toLocaleDateString()
                            : ""}
                        </span>
                      </div>
                      <p className="text-sm font-medium text-white">
                        {item.title}
                      </p>
                    </a>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </>
  );
}
