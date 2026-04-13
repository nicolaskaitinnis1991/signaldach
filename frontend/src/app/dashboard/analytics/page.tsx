"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { BACKEND_URL, type Analytics, type FeedItem } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

const CATEGORY_COLORS: Record<string, string> = {
  regulation: "#9333ea",
  competition: "#f97316",
  market: "#3b82f6",
  sentiment: "#10b981",
};

const URGENCY_COLORS: Record<string, string> = {
  normal: "#94a3b8",
  high: "#f59e0b",
  breaking: "#ef4444",
};

const darkTooltipStyle = {
  contentStyle: { backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", color: "#e2e8f0" },
  labelStyle: { color: "#94a3b8" },
};

export default function AnalyticsPage() {
  const { t, locale } = useTranslation();
  const [data, setData] = useState<Analytics | null>(null);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(true);
  const [regulationItems, setRegulationItems] = useState<FeedItem[]>([]);
  const [sourceData, setSourceData] = useState<
    Array<{ source_name: string; item_count: number }>
  >([]);

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/analytics?days=${days}`);
      const json: Analytics = await res.json();
      setData(json);

      // Source activity data (backend returns source_breakdown)
      if (json.source_breakdown) {
        setSourceData(json.source_breakdown);
      }
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [days]);

  // Load regulation items for timeline
  useEffect(() => {
    async function loadRegulation() {
      try {
        const lp = locale && locale !== "en" ? `&lang=${locale}` : "";
        const res = await fetch(
          `${BACKEND_URL}/items?category=regulation&limit=20&sort=newest${lp}`
        );
        const json = await res.json();
        setRegulationItems(json.items || []);
      } catch {
        setRegulationItems([]);
      }
    }
    loadRegulation();
  }, []);

  useEffect(() => {
    loadAnalytics();
    const interval = setInterval(loadAnalytics, 60000);
    return () => clearInterval(interval);
  }, [loadAnalytics]);

  // Transform daily data for stacked bar chart
  const dailyChartData = data
    ? Object.entries(
        data.daily.reduce(
          (acc, item) => {
            if (!acc[item.day]) acc[item.day] = { day: item.day };
            acc[item.day][item.category] = item.count;
            return acc;
          },
          {} as Record<string, Record<string, unknown>>
        )
      ).map(([, v]) => v)
    : [];

  function handleExport() {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `signaldach-analytics-${days}d-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">{t("analytics.title")}</h2>
          <p className="text-sm text-slate-400 mt-1">
            {t("analytics.subtitle")}
          </p>
        </div>
        <div className="flex gap-2 items-center">
          {[7, 14, 30, 90].map((d) => (
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
          <button
            onClick={handleExport}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-700 text-white hover:bg-slate-600 transition-colors ml-2"
          >
            {t("analytics.exportJson")}
          </button>
        </div>
      </div>

      {loading && !data ? (
        <p className="text-slate-500 text-center py-20">{t("analytics.loadingAnalytics")}</p>
      ) : !data ? (
        <p className="text-slate-500 text-center py-20">
          {t("analytics.noDataAvailable")}
        </p>
      ) : (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-8">
            <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
              <p className="text-2xl font-bold text-white">
                {data.summary.total_items}
              </p>
              <p className="text-xs text-slate-400">{t("common.totalItems")}</p>
            </div>
            <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
              <p className="text-2xl font-bold text-red-500">
                {data.summary.breaking_count}
              </p>
              <p className="text-xs text-slate-400">{t("common.breaking")}</p>
            </div>
            <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
              <p className="text-2xl font-bold text-amber-500">
                {data.summary.high_count}
              </p>
              <p className="text-xs text-slate-400">{t("common.highPriority")}</p>
            </div>
            <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
              <p className="text-2xl font-bold text-blue-400">
                {data.summary.avg_relevance}
              </p>
              <p className="text-xs text-slate-400">{t("common.avgRelevance")}</p>
            </div>
            <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
              <p className="text-2xl font-bold text-green-400">
                {data.summary.avg_sentiment !== null
                  ? data.summary.avg_sentiment.toFixed(2)
                  : "\u2014"}
              </p>
              <p className="text-xs text-slate-400">{t("common.avgSentiment")}</p>
            </div>
          </div>

          {/* Charts Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Daily Items by Category */}
            <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
              <h3 className="font-semibold text-sm text-white mb-4">
                {t("analytics.dailyByCategory")}
              </h3>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={dailyChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis
                    dataKey="day"
                    tick={{ fontSize: 10, fill: "#94a3b8" }}
                    tickFormatter={(v) => v.slice(5)}
                  />
                  <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} />
                  <Tooltip {...darkTooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
                  {Object.entries(CATEGORY_COLORS).map(([cat, color]) => (
                    <Bar
                      key={cat}
                      dataKey={cat}
                      stackId="a"
                      fill={color}
                      name={cat}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Sentiment Trend */}
            <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
              <h3 className="font-semibold text-sm text-white mb-4">
                {t("analytics.sentimentTrend")}
              </h3>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={data.sentiment_trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis
                    dataKey="day"
                    tick={{ fontSize: 10, fill: "#94a3b8" }}
                    tickFormatter={(v) => v.slice(5)}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "#94a3b8" }}
                    domain={[-1, 1]}
                    ticks={[-1, -0.5, 0, 0.5, 1]}
                  />
                  <Tooltip {...darkTooltipStyle} />
                  <Line
                    type="monotone"
                    dataKey="avg_sentiment"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={{ fill: "#10b981", r: 3 }}
                    name={t("analytics.avgSentimentLabel")}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Category Distribution (Pie) */}
            <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
              <h3 className="font-semibold text-sm text-white mb-4">
                {t("analytics.categoryDistribution")}
              </h3>
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={data.by_category}
                    dataKey="count"
                    nameKey="category"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={(props) => `${props.name ?? ""} (${props.value})`}
                    labelLine={false}
                  >
                    {data.by_category.map((entry) => (
                      <Cell
                        key={entry.category}
                        fill={CATEGORY_COLORS[entry.category] || "#94a3b8"}
                      />
                    ))}
                  </Pie>
                  <Tooltip {...darkTooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Top Keywords */}
            <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
              <h3 className="font-semibold text-sm text-white mb-4">
                {t("analytics.topKeywords")}
              </h3>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart
                  data={data.top_keywords.slice(0, 10)}
                  layout="vertical"
                  margin={{ left: 60 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis type="number" tick={{ fontSize: 10, fill: "#94a3b8" }} />
                  <YAxis
                    dataKey="keyword"
                    type="category"
                    tick={{ fontSize: 10, fill: "#94a3b8" }}
                    width={55}
                  />
                  <Tooltip {...darkTooltipStyle} />
                  <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Source Activity */}
            {sourceData.length > 0 && (
              <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
                <h3 className="font-semibold text-sm text-white mb-4">
                  {t("analytics.sourceActivity")}
                </h3>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart
                    data={sourceData.slice(0, 10)}
                    layout="vertical"
                    margin={{ left: 80 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis type="number" tick={{ fontSize: 10, fill: "#94a3b8" }} />
                    <YAxis
                      dataKey="source_name"
                      type="category"
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      width={75}
                    />
                    <Tooltip {...darkTooltipStyle} />
                    <Bar dataKey="item_count" fill="#9333ea" radius={[0, 4, 4, 0]} name={t("analytics.itemsLabel")} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Urgency Breakdown */}
          <div className="mt-6 bg-slate-900 rounded-xl border border-slate-700 p-6">
            <h3 className="font-semibold text-sm text-white mb-4">
              {t("analytics.urgencyBreakdown")}
            </h3>
            <div className="flex gap-4">
              {data.by_urgency.map((u) => (
                <div key={u.urgency} className="flex-1">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-medium text-slate-300">
                      {u.urgency}
                    </span>
                    <span className="text-slate-500">{u.count}</span>
                  </div>
                  <div className="h-3 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${Math.min(100, (u.count / Math.max(data.summary.total_items, 1)) * 100)}%`,
                        backgroundColor:
                          URGENCY_COLORS[u.urgency] || "#94a3b8",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Regulatory Timeline */}
          {regulationItems.length > 0 && (
            <div className="mt-6 bg-slate-900 rounded-xl border border-slate-700 p-6">
              <h3 className="font-semibold text-sm text-white mb-4">
                {t("analytics.regulatoryTimeline")}
              </h3>
              <div className="relative">
                <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-slate-700" />
                <div className="space-y-4">
                  {regulationItems.slice(0, 10).map((item) => (
                    <div key={item.id} className="flex gap-4 ml-2">
                      <div className="relative flex-shrink-0">
                        <div className="w-5 h-5 rounded-full bg-purple-500 border-2 border-slate-900 shadow" />
                      </div>
                      <div className="flex-1 pb-4">
                        <p className="text-xs text-slate-500 mb-1">
                          {item.published_at
                            ? new Date(item.published_at).toLocaleDateString(
                                "de-DE",
                                {
                                  day: "numeric",
                                  month: "short",
                                  year: "numeric",
                                }
                              )
                            : t("analytics.unknownDate")}
                        </p>
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-white hover:text-blue-400 transition-colors"
                        >
                          {item.title}
                        </a>
                        {item.source_name && (
                          <span className="ml-2 text-[10px] text-slate-500">
                            {item.source_name}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
