"use client";

import { useState, useMemo, lazy, Suspense } from "react";
import { useMarketSummary, useMarketPrices, type PriceTick, BACKEND_URL } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import useSWR from "swr";

const PriceChart = lazy(() => import("@/components/PriceChart").then(m => ({ default: m.PriceChart })));
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from "recharts";

const fmt = (n: number | null | undefined, decimals = 2) =>
  n != null ? n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : "—";

const fmtLarge = (n: number | null | undefined) => {
  if (n == null) return "—";
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toLocaleString()}`;
};

const FEAR_GREED_COLOR = (v: number) =>
  v >= 75 ? "#10b981" : v >= 55 ? "#22c55e" : v >= 45 ? "#f59e0b" : v >= 25 ? "#f97316" : "#ef4444";

const FEAR_GREED_BG = (v: number) =>
  v >= 75 ? "bg-emerald-500/10" : v >= 55 ? "bg-green-500/10" : v >= 45 ? "bg-amber-500/10" : v >= 25 ? "bg-orange-500/10" : "bg-red-500/10";

function FearGreedGauge({ value, classification }: { value: number; classification: string }) {
  const color = FEAR_GREED_COLOR(value);
  const radius = 40;
  const circumference = Math.PI * radius;
  const filled = circumference * (value / 100);

  return (
    <div className="flex flex-col items-center">
      <svg width="120" height="70" viewBox="0 0 120 70">
        <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke="#1e293b" strokeWidth="10" strokeLinecap="round" />
        <path
          d="M 10 60 A 50 50 0 0 1 110 60"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference - filled}`}
          style={{ filter: `drop-shadow(0 0 8px ${color}50)` }}
        />
        <text x="60" y="56" textAnchor="middle" fill={color} fontSize="22" fontWeight="900">
          {value}
        </text>
      </svg>
      <span className="text-xs text-slate-400 mt-1">{classification || "N/A"}</span>
    </div>
  );
}

function PriceRow({ tick }: { tick: PriceTick }) {
  const change = tick.change_pct_24h ?? 0;
  const isUp = change > 0;
  const symbol = tick.symbol.split("/")[0];

  return (
    <tr className="border-b border-slate-800 hover:bg-slate-800/50 transition-colors">
      <td className="py-3 px-4">
        <span className="font-semibold text-white">{symbol}</span>
        <span className="text-slate-500 text-xs ml-1">/ USDT</span>
      </td>
      <td className="py-3 px-4 text-right font-mono text-white">
        ${fmt(tick.price)}
      </td>
      <td className={`py-3 px-4 text-right font-mono ${isUp ? "text-emerald-400" : change < 0 ? "text-red-400" : "text-slate-400"}`}>
        {isUp ? "+" : ""}{fmt(change, 1)}%
      </td>
      <td className="py-3 px-4 text-right text-slate-400 text-sm">
        {fmtLarge(tick.volume_24h)}
      </td>
      <td className="py-3 px-4 text-right">
        <div className="w-20 h-6 inline-block">
          <div
            className={`h-full rounded-sm ${isUp ? "bg-emerald-500/20" : "bg-red-500/20"}`}
            style={{ width: `${Math.min(100, Math.abs(change) * 5)}%` }}
          />
        </div>
      </td>
    </tr>
  );
}

export default function MarketPage() {
  const { t } = useTranslation();
  const { data: summary, isLoading: summaryLoading } = useMarketSummary();
  const { data: prices, isLoading: pricesLoading } = useMarketPrices();
  const [sortBy, setSortBy] = useState<"price" | "change" | "volume">("change");

  const sortedPrices = [...(prices?.prices || [])].sort((a, b) => {
    if (sortBy === "price") return b.price - a.price;
    if (sortBy === "change") return Math.abs(b.change_pct_24h ?? 0) - Math.abs(a.change_pct_24h ?? 0);
    return (b.volume_24h ?? 0) - (a.volume_24h ?? 0);
  });

  // Top movers for the bar chart
  const topMovers = [...(prices?.prices || [])]
    .filter((p) => p.change_pct_24h != null)
    .sort((a, b) => Math.abs(b.change_pct_24h!) - Math.abs(a.change_pct_24h!))
    .slice(0, 12)
    .map((p) => ({
      symbol: p.symbol.split("/")[0],
      change: p.change_pct_24h!,
    }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">{t("marketPage.title")}</h1>
        <p className="text-slate-400 text-sm mt-1">{t("marketPage.subtitle")}</p>
      </div>

      {/* Key Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* BTC Price */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
          <p className="text-xs text-slate-400 uppercase tracking-wider">Bitcoin</p>
          {summaryLoading ? (
            <div className="h-8 bg-slate-800 rounded animate-pulse mt-2" />
          ) : (
            <>
              <p className="text-2xl font-bold text-white mt-1">
                ${fmt(summary?.btc?.price)}
              </p>
              <p className={`text-sm mt-1 ${(summary?.btc?.change_pct_24h ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {(summary?.btc?.change_pct_24h ?? 0) >= 0 ? "+" : ""}
                {fmt(summary?.btc?.change_pct_24h, 1)}% 24h
              </p>
            </>
          )}
        </div>

        {/* ETH Price */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
          <p className="text-xs text-slate-400 uppercase tracking-wider">Ethereum</p>
          {summaryLoading ? (
            <div className="h-8 bg-slate-800 rounded animate-pulse mt-2" />
          ) : (
            <>
              <p className="text-2xl font-bold text-white mt-1">
                ${fmt(summary?.eth?.price)}
              </p>
              <p className={`text-sm mt-1 ${(summary?.eth?.change_pct_24h ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {(summary?.eth?.change_pct_24h ?? 0) >= 0 ? "+" : ""}
                {fmt(summary?.eth?.change_pct_24h, 1)}% 24h
              </p>
            </>
          )}
        </div>

        {/* Fear & Greed */}
        <div className={`bg-slate-900 rounded-xl border border-slate-700 p-5 ${summary?.fear_greed ? FEAR_GREED_BG(summary.fear_greed.value) : ""}`}>
          <p className="text-xs text-slate-400 uppercase tracking-wider">Fear & Greed</p>
          {summaryLoading ? (
            <div className="h-16 bg-slate-800 rounded animate-pulse mt-2" />
          ) : summary?.fear_greed ? (
            <FearGreedGauge value={summary.fear_greed.value} classification={summary.fear_greed.classification} />
          ) : (
            <p className="text-slate-500 mt-2">{t("marketPage.noData")}</p>
          )}
        </div>

        {/* Global Metrics */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
          <p className="text-xs text-slate-400 uppercase tracking-wider">{t("marketPage.global")}</p>
          {summaryLoading ? (
            <div className="h-8 bg-slate-800 rounded animate-pulse mt-2" />
          ) : (
            <>
              <p className="text-lg font-bold text-white mt-1">
                {fmtLarge(summary?.global?.total_market_cap)}
              </p>
              <p className="text-xs text-slate-400 mt-1">{t("marketPage.totalMarketCap")}</p>
              <p className="text-sm text-blue-400 mt-2">
                {t("marketPage.btcDom")}: {fmt(summary?.global?.btc_dominance, 1)}%
              </p>
            </>
          )}
        </div>
      </div>

      {/* BTC Price Chart (TradingView Lightweight) */}
      <BtcPriceChart title={t("marketPage.btc30day")} />

      {/* Top Movers Chart */}
      {topMovers.length > 0 && (
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
          <h2 className="text-sm font-semibold text-white mb-4">{t("marketPage.topMovers24h")}</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={topMovers} layout="vertical" margin={{ left: 40 }}>
              <XAxis type="number" tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`} stroke="#64748b" fontSize={11} />
              <YAxis type="category" dataKey="symbol" stroke="#94a3b8" fontSize={11} width={50} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#fff", fontSize: 12 }}
                formatter={(v) => [`${Number(v) > 0 ? "+" : ""}${Number(v).toFixed(2)}%`, t("marketPage.change")]}
              />
              <Bar dataKey="change" radius={[0, 4, 4, 0]}>
                {topMovers.map((entry, index) => (
                  <Cell key={index} fill={entry.change >= 0 ? "#10b981" : "#ef4444"} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Price Table */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-700 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">{t("marketPage.allPrices")}</h2>
          <div className="flex gap-2">
            {(["change", "price", "volume"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSortBy(s)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                  sortBy === s ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400 hover:text-white"
                }`}
              >
                {s === "change" ? t("marketPage.movers") : s === "price" ? t("marketPage.price") : t("marketPage.volume")}
              </button>
            ))}
          </div>
        </div>
        {pricesLoading ? (
          <div className="p-8 text-center text-slate-500">{t("marketPage.loadingPrices")}</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-xs text-slate-500 uppercase tracking-wider">
                <th className="py-2 px-4 text-left">{t("marketPage.asset")}</th>
                <th className="py-2 px-4 text-right">{t("marketPage.price")}</th>
                <th className="py-2 px-4 text-right">{t("marketPage.change24h")}</th>
                <th className="py-2 px-4 text-right">{t("marketPage.volume")}</th>
                <th className="py-2 px-4 text-right">{t("marketPage.trend")}</th>
              </tr>
            </thead>
            <tbody>
              {sortedPrices.map((tick) => (
                <PriceRow key={tick.symbol} tick={tick} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// BTC Price Chart (lazy-loaded TradingView lightweight-charts)
// ---------------------------------------------------------------------------
async function priceFetcher<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

function BtcPriceChart({ title }: { title: string }) {
  const { data: priceHistory } = useSWR<{ prices: Array<{ ts: string; price: number; volume_24h: number | null }> }>(
    `${BACKEND_URL}/api/market/prices/history?symbol=BTC/USDT&days=30&limit=500`,
    priceFetcher,
    { revalidateOnFocus: false, refreshInterval: 300000 }
  );

  const chartData = useMemo(() => {
    if (!priceHistory?.prices?.length) return null;
    const lineData = priceHistory.prices
      .map(p => ({
        time: p.ts.split("T")[0],
        value: p.price,
      }))
      .reduce((acc, item) => {
        acc.set(item.time, item);
        return acc;
      }, new Map<string, { time: string; value: number }>());

    return Array.from(lineData.values()).sort((a, b) => a.time.localeCompare(b.time));
  }, [priceHistory]);

  if (!chartData || chartData.length < 2) return null;

  return (
    <Suspense fallback={<div className="h-[360px] bg-slate-900 rounded-xl border border-slate-800 animate-pulse" />}>
      <PriceChart
        data={chartData}
        mode="area"
        height={360}
        title={title}
      />
    </Suspense>
  );
}
