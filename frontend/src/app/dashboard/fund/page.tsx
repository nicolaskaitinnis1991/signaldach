"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import { BACKEND_URL } from "@/lib/api";
import { authFetch } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import {
  PieChart, Pie, Cell, ResponsiveContainer,
  AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar,
} from "recharts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface RiskBreach { check: string; message: string; severity: string }
interface RiskWarning { check: string; message: string }
interface FundDashboardData {
  fund_name: string;
  total_value: number;
  cash_usd: number;
  position_count: number;
  allocation: Record<string, number>;
  sector_allocation: Record<string, number>;
  breaches: RiskBreach[];
  warnings: RiskWarning[];
  halt_trading: boolean;
  signal_summary: { latest_score: number; confidence: number; ts: string } | null;
  scorecard_summary: { win_rate: number; avg_return_pct: number; signal_sharpe: number; total_signals: number } | null;
}

// ---------------------------------------------------------------------------
// Sample fund data (demo mode when backend doesn't have real positions)
// ---------------------------------------------------------------------------
const DEMO_POSITIONS = [
  { symbol: "BTC/USDT", quantity: 2.5, entry_price: 42000 },
  { symbol: "ETH/USDT", quantity: 20, entry_price: 2800 },
  { symbol: "SOL/USDT", quantity: 100, entry_price: 95 },
];

const PIE_COLORS = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444", "#6366f1", "#ec4899"];

// ---------------------------------------------------------------------------
// Fetcher with auth
// ---------------------------------------------------------------------------
async function authJsonFetcher<T>(url: string): Promise<T> {
  const res = await authFetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function postFetcher<T>([url, body]: [string, object]): Promise<T> {
  const res = await authFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function FundDashboardPage() {
  const { t } = useTranslation();
  const [cashUsd] = useState(50000);

  const fundPayload = useMemo(() => ({
    positions: DEMO_POSITIONS,
    cash_usd: cashUsd,
    fund_name: "SignalDACH Fund I",
    high_water_mark: 0,
  }), [cashUsd]);

  const { data: dashboard, isLoading } = useSWR<FundDashboardData>(
    [`${BACKEND_URL}/api/fund/dashboard`, fundPayload],
    ([url, body]: [string, object]) => postFetcher([url, body]),
    { refreshInterval: 60000, revalidateOnFocus: false }
  );

  const { data: riskLimits } = useSWR<{ limits: Record<string, number> }>(
    `${BACKEND_URL}/api/fund/risk-limits`,
    authJsonFetcher,
  );

  // Scorecard from dedicated endpoint
  const { data: scorecard } = useSWR(
    `${BACKEND_URL}/api/scorecard/performance?symbol=BTC/USDT&signal_type=composite&days=30`,
    authJsonFetcher<Record<string, unknown>>,
    { refreshInterval: 300000 }
  );

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-64 bg-slate-800 rounded" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <div key={i} className="h-28 bg-slate-800 rounded-xl" />)}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="h-72 bg-slate-800 rounded-xl" />
          <div className="h-72 bg-slate-800 rounded-xl" />
        </div>
      </div>
    );
  }

  const totalValue = dashboard?.total_value ?? 0;
  const cash = dashboard?.cash_usd ?? cashUsd;
  const haltTrading = dashboard?.halt_trading ?? false;
  const breaches = dashboard?.breaches ?? [];
  const warnings = dashboard?.warnings ?? [];
  const signal = dashboard?.signal_summary;
  const sc = dashboard?.scorecard_summary;

  // Allocation pie data
  const allocationData = Object.entries(dashboard?.allocation ?? {}).map(([name, value]) => ({
    name: name.split("/")[0],
    value: Math.round(value * 100) / 100,
  }));
  if (cash > 0 && totalValue > 0) {
    allocationData.push({ name: "Cash", value: Math.round((cash / totalValue) * 10000) / 100 });
  }

  // Sector pie data
  const sectorData = Object.entries(dashboard?.sector_allocation ?? {}).map(([name, value]) => ({
    name,
    value: Math.round(value * 100) / 100,
  }));

  // Signal score display
  const signalScore = signal?.latest_score ?? 0;
  const signalColor = signalScore > 0.3 ? "text-green-400" : signalScore < -0.3 ? "text-red-400" : "text-yellow-400";
  const signalLabel = signalScore > 0.3 ? t("fundPage.bullish") : signalScore < -0.3 ? t("fundPage.bearish") : t("fundPage.neutral");

  // Limits
  const limits = riskLimits?.limits ?? {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{dashboard?.fund_name ?? t("fundPage.title")}</h1>
          <p className="text-slate-400 text-sm mt-1">{t("fundPage.subtitle")}</p>
        </div>
        {haltTrading && (
          <div className="px-4 py-2 bg-red-500/20 border border-red-500/50 rounded-lg animate-pulse" role="alert" aria-live="assertive">
            <span className="text-red-400 font-bold text-sm">{t("fundPage.tradingHalted")}</span>
          </div>
        )}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label={t("fundPage.totalAum")}
          value={`$${(totalValue).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
          sub={`${dashboard?.position_count ?? 0} ${t("fundPage.positions")}`}
          color="blue"
        />
        <KpiCard
          label={t("fundPage.cashReserve")}
          value={`$${cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
          sub={totalValue > 0 ? `${((cash / totalValue) * 100).toFixed(1)}% ${t("fundPage.ofAum")}` : ""}
          color={totalValue > 0 && (cash / totalValue) * 100 < (limits.min_cash_reserve_pct ?? 10) ? "red" : "green"}
        />
        <KpiCard
          label={t("fundPage.signal")}
          value={signalLabel}
          sub={signal ? `${t("fundPage.score")}: ${signalScore.toFixed(2)} | ${t("fundPage.conf")}: ${((signal.confidence ?? 0) * 100).toFixed(0)}%` : t("fundPage.noData")}
          color={signalScore > 0.3 ? "green" : signalScore < -0.3 ? "red" : "yellow"}
        />
        <KpiCard
          label={t("fundPage.winRate")}
          value={sc ? `${(sc.win_rate * 100).toFixed(1)}%` : "N/A"}
          sub={sc ? `${sc.total_signals} ${t("fundPage.signals")} | ${t("fundPage.sharpe")}: ${sc.signal_sharpe.toFixed(2)}` : t("fundPage.insufficientData")}
          color={sc && sc.win_rate > 0.55 ? "green" : "yellow"}
        />
      </div>

      {/* Risk Alerts */}
      {(breaches.length > 0 || warnings.length > 0) && (
        <div className="space-y-2">
          {breaches.map((b, i) => (
            <div key={`b-${i}`} className="flex items-center gap-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
              <svg className="w-5 h-5 text-red-400 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
              <div>
                <span className="text-sm font-medium text-red-400">{b.check}</span>
                <p className="text-xs text-red-300/80">{b.message}</p>
              </div>
            </div>
          ))}
          {warnings.map((w, i) => (
            <div key={`w-${i}`} className="flex items-center gap-3 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
              <svg className="w-5 h-5 text-yellow-400 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              <div>
                <span className="text-sm font-medium text-yellow-400">{w.check}</span>
                <p className="text-xs text-yellow-300/80">{w.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Allocation Pie */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 className="text-sm font-semibold text-white mb-4">{t("fundPage.portfolioAllocation")}</h3>
          {allocationData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={allocationData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={2}
                  dataKey="value"
                  label={({ name, value }) => `${name} ${value}%`}
                >
                  {allocationData.map((_, idx) => (
                    <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px" }}
                  itemStyle={{ color: "#e2e8f0" }}
                  formatter={(v) => [`${Number(v).toFixed(2)}%`, t("fundPage.allocation")]}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-52 text-slate-500 text-sm">{t("fundPage.noPositionData")}</div>
          )}
        </div>

        {/* Sector Allocation */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 className="text-sm font-semibold text-white mb-4">{t("fundPage.sectorExposure")}</h3>
          {sectorData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={sectorData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
                <YAxis type="category" dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} width={120} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px" }}
                  itemStyle={{ color: "#e2e8f0" }}
                  formatter={(v) => [`${Number(v).toFixed(1)}%`, t("fundPage.exposure")]}
                />
                <Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-52 text-slate-500 text-sm">{t("fundPage.noSectorData")}</div>
          )}
        </div>
      </div>

      {/* Risk Limits Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-white mb-4">{t("fundPage.riskLimits")}</h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {/* Backend returns values already as percentages (e.g. 25.0 = 25%) */}
          <LimitGauge label={t("fundPage.maxPosition")} value={limits.max_position_pct ?? 25} unit="%" />
          <LimitGauge label={t("fundPage.maxSector")} value={limits.max_sector_pct ?? 40} unit="%" />
          <LimitGauge label={t("fundPage.maxDrawdown")} value={limits.max_drawdown_pct ?? 15} unit="%" color="red" />
          <LimitGauge label={t("fundPage.cashReserve")} value={limits.min_cash_reserve_pct ?? 10} unit="%" color="green" />
          <LimitGauge label={t("fundPage.minCapital")} value={(limits.min_capital_eur ?? 125000) / 1000} unit="K EUR" color="blue" />
        </div>
      </div>

      {/* Scorecard Summary */}
      {scorecard && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 className="text-sm font-semibold text-white mb-4">{t("fundPage.scorecard30d")}</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-white">
                {typeof scorecard.total_signals === "number" ? scorecard.total_signals : "—"}
              </p>
              <p className="text-xs text-slate-400">{t("fundPage.totalSignals")}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-green-400">
                {typeof scorecard.win_rate === "number" ? `${(scorecard.win_rate as number * 100).toFixed(1)}%` : "—"}
              </p>
              <p className="text-xs text-slate-400">{t("fundPage.winRate")}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-blue-400">
                {typeof scorecard.avg_return_pct === "number" ? `${(scorecard.avg_return_pct as number).toFixed(2)}%` : "—"}
              </p>
              <p className="text-xs text-slate-400">{t("fundPage.avgReturn")}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-purple-400">
                {typeof scorecard.signal_sharpe === "number" ? (scorecard.signal_sharpe as number).toFixed(2) : "—"}
              </p>
              <p className="text-xs text-slate-400">{t("fundPage.sharpeRatio")}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function KpiCard({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  const borderColors: Record<string, string> = {
    blue: "border-blue-500/30",
    green: "border-green-500/30",
    red: "border-red-500/30",
    yellow: "border-yellow-500/30",
  };
  const valueColors: Record<string, string> = {
    blue: "text-blue-400",
    green: "text-green-400",
    red: "text-red-400",
    yellow: "text-yellow-400",
  };

  return (
    <div className={`bg-slate-900 border ${borderColors[color] ?? "border-slate-800"} rounded-xl p-4`}>
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className={`text-xl font-bold ${valueColors[color] ?? "text-white"}`}>{value}</p>
      <p className="text-[11px] text-slate-500 mt-1">{sub}</p>
    </div>
  );
}

function LimitGauge({ label, value, unit, color = "slate" }: { label: string; value: number; unit: string; color?: string }) {
  const textColor: Record<string, string> = {
    red: "text-red-400",
    green: "text-green-400",
    blue: "text-blue-400",
    slate: "text-white",
  };

  return (
    <div className="text-center">
      <p className={`text-2xl font-bold ${textColor[color] ?? "text-white"}`}>
        {value.toFixed(value >= 100 ? 0 : 1)}{unit.startsWith("%") ? "" : " "}{unit}
      </p>
      <p className="text-xs text-slate-400 mt-1">{label}</p>
    </div>
  );
}
