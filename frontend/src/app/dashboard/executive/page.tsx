"use client";

import { useEffect, useState } from "react";
import { BACKEND_URL, type FeedItem, type Analytics, stripHtml, timeAgo } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, CartesianGrid, Legend,
  AreaChart, Area,
} from "recharts";

const COLORS = {
  regulation: "#8b5cf6",
  market: "#3b82f6",
  competition: "#f59e0b",
  sentiment: "#10b981",
  breaking: "#ef4444",
  high: "#f59e0b",
  normal: "#64748b",
};

const SENTIMENT_COLOR = (v: number) =>
  v > 0.2 ? "#10b981" : v < -0.2 ? "#ef4444" : "#f59e0b";

interface IntelReport {
  executive_summary: string;
  market_risk_score: number;
  market_risk_label: string;
  sentiment_assessment: string;
  regulatory_risk_de: { score: number; summary: string };
  regulatory_risk_ch: { score: number; summary: string };
  key_events: Array<{ title: string; impact: string; description: string }>;
  action_items: string[];
  market_outlook: string;
  dach_specific: string;
  _meta?: { model: string; type: string; generated_at: string; total_signals: number };
}

const RISK_COLOR = (score: number) =>
  score >= 80 ? "#ef4444" : score >= 60 ? "#f97316" : score >= 40 ? "#f59e0b" : score >= 20 ? "#3b82f6" : "#10b981";

function RiskGauge({ score, label }: { score: number; label: string }) {
  const color = RISK_COLOR(score);
  const pct = Math.min(100, Math.max(0, score)) / 100;
  // Semi-circle: total arc from -90deg to +90deg = 180deg
  // strokeDasharray = circumference of the half-circle
  const radius = 40;
  const circumference = Math.PI * radius; // half-circle
  const filled = circumference * pct;
  const gap = circumference - filled;

  return (
    <div className="flex flex-col items-center">
      <svg width="100" height="58" viewBox="0 0 100 58">
        {/* Background arc */}
        <path
          d="M 10 50 A 40 40 0 0 1 90 50"
          fill="none"
          stroke="#1e293b"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {/* Colored arc */}
        <path
          d="M 10 50 A 40 40 0 0 1 90 50"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${gap}`}
          style={{ filter: `drop-shadow(0 0 6px ${color}60)` }}
        />
        {/* Score text */}
        <text
          x="50"
          y="46"
          textAnchor="middle"
          fill={color}
          fontSize="20"
          fontWeight="900"
        >
          {score}
        </text>
      </svg>
      <div className="text-[10px] text-slate-400 uppercase tracking-wider -mt-1">{label}</div>
    </div>
  );
}

const darkTooltipStyle = {
  contentStyle: { backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", color: "#e2e8f0" },
  labelStyle: { color: "#94a3b8" },
};

export default function ExecutivePage() {
  const { t, locale } = useTranslation();
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [breaking, setBreaking] = useState<FeedItem[]>([]);
  const [topRegulation, setTopRegulation] = useState<FeedItem[]>([]);
  const [topMarket, setTopMarket] = useState<FeedItem[]>([]);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [report, setReport] = useState<IntelReport | null>(null);
  const [reportLoading, setReportLoading] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const lp = locale && locale !== "en" ? `&lang=${locale}` : "";
        const [analyticsRes, breakingRes, regRes, marketRes, healthRes] = await Promise.all([
          fetch(`${BACKEND_URL}/analytics?days=7`).then((r) => r.json()),
          fetch(`${BACKEND_URL}/items?urgency=breaking&limit=5${lp}`).then((r) => r.json()),
          fetch(`${BACKEND_URL}/items?category=regulation&limit=5&sort=relevance${lp}`).then((r) => r.json()),
          fetch(`${BACKEND_URL}/items?category=market&limit=5&sort=relevance${lp}`).then((r) => r.json()),
          fetch(`${BACKEND_URL}/monitoring/health`).then((r) => r.json()).catch(() => null),
        ]);
        setAnalytics(analyticsRes);
        setBreaking(breakingRes.items || []);
        setTopRegulation(regRes.items || []);
        setTopMarket(marketRes.items || []);
        setHealth(healthRes);
      } catch (e) {
        console.error("Failed to load executive data:", e);
      } finally {
        setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 60000);
    return () => clearInterval(interval);
  }, []);

  // Load AI Report separately (may take longer)
  useEffect(() => {
    async function loadReport() {
      setReportLoading(true);
      try {
        const res = await fetch(`${BACKEND_URL}/report?hours=24`);
        const data = await res.json();
        setReport(data);
      } catch (e) {
        console.error("Failed to load report:", e);
      } finally {
        setReportLoading(false);
      }
    }
    loadReport();
    const interval = setInterval(loadReport, 300000); // every 5 min
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-slate-400 text-lg">{t("executive.loadingExecSummary")}</div>
      </div>
    );
  }

  if (!analytics) return <div className="text-red-500">{t("executive.failedToLoad")}</div>;

  const { summary, by_category, daily, sentiment_trend, top_keywords } = analytics;
  const sentimentLabel =
    (summary.avg_sentiment ?? 0) > 0.1 ? t("executive.bullish") :
    (summary.avg_sentiment ?? 0) < -0.1 ? t("executive.bearish") : t("executive.neutral");
  const sentimentColor = SENTIMENT_COLOR(summary.avg_sentiment ?? 0);

  const categoryData = by_category.map((c) => ({
    name: c.category.charAt(0).toUpperCase() + c.category.slice(1),
    value: c.count,
    color: COLORS[c.category as keyof typeof COLORS] || "#64748b",
  }));

  const dailyAgg: Record<string, Record<string, number>> = {};
  (daily || []).forEach((d) => {
    if (!dailyAgg[d.day]) dailyAgg[d.day] = {};
    dailyAgg[d.day][d.category] = d.count;
  });
  const dailyChart = Object.entries(dailyAgg)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, cats]) => ({
      day: day.slice(5),
      regulation: cats.regulation || 0,
      market: cats.market || 0,
      competition: cats.competition || 0,
    }));

  const sentimentChart = (sentiment_trend || []).map((s) => ({
    day: s.day.slice(5),
    sentiment: Number(s.avg_sentiment?.toFixed(3) ?? 0),
    volume: s.count,
  }));

  const keywordData = (top_keywords || []).slice(0, 15);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-white">{t("executive.title")}</h1>
          <p className="text-sm text-slate-400 mt-1">
            {t("executive.subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-slate-400">{t("common.live")}</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-4 transition-all duration-300 hover:scale-105 hover:border-blue-500/50">
          <p className="text-3xl font-bold text-white">{summary.total_items}</p>
          <p className="text-xs text-slate-400 mt-1">{t("executive.totalSignals")}</p>
        </div>
        <div className="bg-slate-900 rounded-xl border border-red-800 p-4 transition-all duration-300 hover:scale-105 hover:border-red-500/50">
          <p className="text-3xl font-bold text-red-500">{summary.breaking_count}</p>
          <p className="text-xs text-slate-400 mt-1">{t("common.breakingAlerts")}</p>
        </div>
        <div className="bg-slate-900 rounded-xl border border-amber-800 p-4 transition-all duration-300 hover:scale-105 hover:border-amber-500/50">
          <p className="text-3xl font-bold text-amber-500">{summary.high_count}</p>
          <p className="text-xs text-slate-400 mt-1">{t("common.highPriority")}</p>
        </div>
        <div className="bg-slate-900 rounded-xl border border-blue-800 p-4 transition-all duration-300 hover:scale-105 hover:border-blue-500/50">
          <p className="text-3xl font-bold text-blue-400">{summary.avg_relevance}</p>
          <p className="text-xs text-slate-400 mt-1">{t("common.avgRelevance")}</p>
        </div>
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-4 transition-all duration-300 hover:scale-105 hover:border-blue-500/50" style={{ borderColor: sentimentColor + "40" }}>
          <p className="text-3xl font-bold" style={{ color: sentimentColor }}>
            {(summary.avg_sentiment ?? 0).toFixed(2)}
          </p>
          <p className="text-xs text-slate-400 mt-1">{t("common.avgSentiment")} ({sentimentLabel})</p>
        </div>
        <div className="bg-slate-900 rounded-xl border border-purple-800 p-4 transition-all duration-300 hover:scale-105 hover:border-purple-500/50">
          <p className="text-3xl font-bold text-purple-400">
            {by_category.find((c) => c.category === "regulation")?.count || 0}
          </p>
          <p className="text-xs text-slate-400 mt-1">{t("common.regulatoryEvents")}</p>
        </div>
      </div>

      {/* AI Intelligence Report */}
      {reportLoading ? (
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
          <div className="animate-pulse flex items-center gap-2">
            <div className="w-4 h-4 bg-blue-800 rounded-full" />
            <span className="text-sm text-slate-400">{t("executive.generatingReport")}</span>
          </div>
        </div>
      ) : report ? (
        <div className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden transition-colors duration-200">
          {/* Report Header */}
          <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between border-b border-slate-700">
            <div>
              <h3 className="text-sm font-bold tracking-wider uppercase">{t("executive.dailyReport")}</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                {report._meta?.generated_at ? new Date(report._meta.generated_at).toLocaleString() : t("executive.justNow")}
                {" "} — {t("executive.poweredBy")} {report._meta?.type === "ai" ? report._meta.model : t("executive.ruleEngine")}
              </p>
            </div>
            <div className="flex items-center gap-4">
              <RiskGauge score={report.market_risk_score} label={t("executive.marketRisk")} />
              <div
                className="px-3 py-1 rounded-full text-xs font-bold"
                style={{
                  backgroundColor: RISK_COLOR(report.market_risk_score) + "20",
                  color: RISK_COLOR(report.market_risk_score),
                }}
              >
                {report.market_risk_label}
              </div>
            </div>
          </div>

          {/* Executive Summary */}
          <div className="px-6 py-4 border-b border-slate-700">
            <p className="text-sm text-slate-300 leading-relaxed">{report.executive_summary}</p>
          </div>

          {/* Risk Gauges */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-0 border-b border-slate-700">
            <div className="px-6 py-4 border-r border-slate-700">
              <p className="text-xs text-slate-400 uppercase font-semibold mb-1">{t("executive.marketSentiment")}</p>
              <p className="text-sm text-slate-300">{report.sentiment_assessment}</p>
            </div>
            <div className="px-6 py-4 border-r border-slate-700">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs text-slate-400 uppercase font-semibold">{t("executive.deRegulatoryRisk")}</p>
                <span className="text-sm font-bold" style={{ color: RISK_COLOR(report.regulatory_risk_de.score) }}>
                  {report.regulatory_risk_de.score}/100
                </span>
              </div>
              <p className="text-sm text-slate-300">{report.regulatory_risk_de.summary}</p>
            </div>
            <div className="px-6 py-4">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs text-slate-400 uppercase font-semibold">{t("executive.chRegulatoryRisk")}</p>
                <span className="text-sm font-bold" style={{ color: RISK_COLOR(report.regulatory_risk_ch.score) }}>
                  {report.regulatory_risk_ch.score}/100
                </span>
              </div>
              <p className="text-sm text-slate-300">{report.regulatory_risk_ch.summary}</p>
            </div>
          </div>

          {/* Key Events + Action Items */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-0">
            <div className="px-6 py-4 border-r border-slate-700">
              <p className="text-xs text-slate-400 uppercase font-semibold mb-3">{t("executive.keyEvents")}</p>
              <div className="space-y-2">
                {(report.key_events || []).map((evt, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className={`flex-shrink-0 mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold ${
                      evt.impact === "HIGH" ? "bg-red-950/50 text-red-400" :
                      evt.impact === "MEDIUM" ? "bg-amber-950/50 text-amber-400" :
                      "bg-slate-800 text-slate-400"
                    }`}>
                      {evt.impact}
                    </span>
                    <div>
                      <p className="text-sm text-slate-200 font-medium leading-tight">{evt.title}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{evt.description}</p>
                    </div>
                  </div>
                ))}
                {(!report.key_events || report.key_events.length === 0) && (
                  <p className="text-sm text-slate-500">{t("executive.noSignificantEvents")}</p>
                )}
              </div>
            </div>
            <div className="px-6 py-4">
              <p className="text-xs text-slate-400 uppercase font-semibold mb-3">{t("executive.actionItems")}</p>
              <div className="space-y-2">
                {(report.action_items || []).map((action, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="flex-shrink-0 mt-1 w-5 h-5 rounded-full bg-blue-950/50 text-blue-400 text-[10px] font-bold flex items-center justify-center">
                      {i + 1}
                    </span>
                    <p className="text-sm text-slate-300">{action}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Market Outlook + DACH */}
          <div className="px-6 py-4 bg-slate-800/50 border-t border-slate-700">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-slate-400 uppercase font-semibold mb-1">{t("executive.marketOutlook")}</p>
                <p className="text-sm text-slate-300">{report.market_outlook}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400 uppercase font-semibold mb-1">{t("executive.dachRegion")}</p>
                <p className="text-sm text-slate-300">{report.dach_specific}</p>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {/* Breaking Alerts Banner */}
      {breaking.length > 0 && (
        <div className="bg-red-950/50 border border-red-800 rounded-xl p-4">
          <h3 className="text-sm font-bold text-red-400 mb-3 flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            {t("executive.breakingAlerts")}
          </h3>
          <div className="space-y-2">
            {breaking.map((item) => (
              <a
                key={item.id}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block text-sm text-red-300 hover:text-red-200 font-medium"
              >
                {stripHtml(item.title)}
                <span className="text-red-500 text-xs ml-2">{timeAgo(item.published_at)}</span>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Charts Row 1: Activity + Categories */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Daily Activity */}
        <div className="lg:col-span-2 bg-slate-900 rounded-xl border border-slate-700 p-5 transition-colors duration-200">
          <h3 className="text-sm font-bold text-slate-300 mb-4">{t("executive.signalVolume")}</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={dailyChart}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <Tooltip {...darkTooltipStyle} />
              <Legend iconSize={8} wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
              <Bar dataKey="regulation" stackId="a" fill={COLORS.regulation} name={t("executive.regulation")} />
              <Bar dataKey="market" stackId="a" fill={COLORS.market} name={t("executive.market")} />
              <Bar dataKey="competition" stackId="a" fill={COLORS.competition} name={t("executive.competition")} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Category Distribution */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5 transition-colors duration-200">
          <h3 className="text-sm font-bold text-slate-300 mb-4">{t("executive.signalDistribution")}</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={categoryData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={3}
              >
                {categoryData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip {...darkTooltipStyle} />
              <Legend iconSize={8} wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts Row 2: Sentiment + Keywords */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Sentiment Trend */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5 transition-colors duration-200">
          <h3 className="text-sm font-bold text-slate-300 mb-4">{t("executive.sentimentTrend")}</h3>
          {sentimentChart.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={sentimentChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <YAxis domain={[-1, 1]} tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <Tooltip {...darkTooltipStyle} />
                <defs>
                  <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="sentiment" stroke="#3b82f6" fill="url(#sentGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-slate-500 py-10 text-center">{t("executive.notEnoughData")}</p>
          )}
        </div>

        {/* Top Keywords */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5 transition-colors duration-200">
          <h3 className="text-sm font-bold text-slate-300 mb-4">{t("executive.trendingKeywords")}</h3>
          {keywordData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={keywordData} layout="vertical" margin={{ left: 80 }}>
                <XAxis type="number" tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <YAxis dataKey="keyword" type="category" tick={{ fontSize: 10, fill: "#94a3b8" }} width={75} />
                <Tooltip {...darkTooltipStyle} />
                <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-slate-500 py-10 text-center">{t("executive.noKeywordData")}</p>
          )}
        </div>
      </div>

      {/* Intelligence Briefs Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top Regulatory */}
        <div className="bg-slate-900 rounded-xl border border-purple-800 p-5 transition-colors duration-200">
          <h3 className="text-sm font-bold text-purple-400 mb-3">{t("executive.regulatoryIntelligence")}</h3>
          <div className="space-y-3">
            {topRegulation.length > 0 ? topRegulation.map((item) => (
              <a
                key={item.id}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block group"
              >
                <div className="flex items-start gap-2">
                  <span className="flex-shrink-0 mt-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-950/50 text-purple-400">
                    {item.relevance_score}/10
                  </span>
                  <div>
                    <p className="text-sm text-slate-200 group-hover:text-purple-400 font-medium leading-tight">
                      {stripHtml(item.title).slice(0, 100)}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {item.author || item.source_id} — {timeAgo(item.published_at)}
                    </p>
                  </div>
                </div>
              </a>
            )) : (
              <p className="text-sm text-slate-500">{t("executive.noRegulatoryEvents")}</p>
            )}
          </div>
        </div>

        {/* Top Market */}
        <div className="bg-slate-900 rounded-xl border border-blue-800 p-5 transition-colors duration-200">
          <h3 className="text-sm font-bold text-blue-400 mb-3">{t("executive.marketIntelligence")}</h3>
          <div className="space-y-3">
            {topMarket.length > 0 ? topMarket.map((item) => (
              <a
                key={item.id}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block group"
              >
                <div className="flex items-start gap-2">
                  <span className="flex-shrink-0 mt-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-950/50 text-blue-400">
                    {item.relevance_score}/10
                  </span>
                  <div>
                    <p className="text-sm text-slate-200 group-hover:text-blue-400 font-medium leading-tight">
                      {stripHtml(item.title).slice(0, 100)}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {item.author || item.source_id} — {timeAgo(item.published_at)}
                    </p>
                  </div>
                </div>
              </a>
            )) : (
              <p className="text-sm text-slate-500">{t("executive.noMarketEvents")}</p>
            )}
          </div>
        </div>
      </div>

      {/* System Status Footer */}
      <div className="bg-slate-800 rounded-xl p-4 flex flex-wrap items-center gap-6 text-xs text-slate-400">
        <span>Sources: <strong className="text-slate-300">{String(health?.sources_total ?? "—")}</strong> active</span>
        <span>Last Scrape: <strong className="text-slate-300">{health?.last_scrape ? timeAgo(String(health.last_scrape)) : "—"}</strong></span>
        <span>DB Items: <strong className="text-slate-300">{summary.total_items}</strong></span>
        <span>Auto-refresh: <strong className="text-slate-300">60s</strong></span>
        <span className="ml-auto text-[10px] text-slate-500">SignalDACH v0.3.0 — Executive Intelligence</span>
      </div>
    </div>
  );
}
