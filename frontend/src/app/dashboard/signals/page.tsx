"use client";

import { useState } from "react";
import { BACKEND_URL, useSignalAnalysis, useMarketRegime, useAnomalies, useScorecard } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, Cell,
} from "recharts";

const SIGNAL_COLORS: Record<string, string> = {
  strong_buy: "#10b981",
  buy: "#22c55e",
  neutral: "#f59e0b",
  sell: "#f97316",
  strong_sell: "#ef4444",
};

const SIGNAL_LABEL_KEYS: Record<string, string> = {
  strong_buy: "signalsPage.strongBuy",
  buy: "signalsPage.buy",
  neutral: "signalsPage.neutralSignal",
  sell: "signalsPage.sell",
  strong_sell: "signalsPage.strongSell",
};

const REGIME_COLORS: Record<string, string> = {
  risk_on: "#10b981",
  risk_off: "#ef4444",
  accumulation: "#3b82f6",
  distribution: "#f97316",
  transition: "#f59e0b",
  unknown: "#64748b",
};

function SignalBadge({ signal }: { signal: string }) {
  const { t } = useTranslation();
  const color = SIGNAL_COLORS[signal] || "#64748b";
  const key = SIGNAL_LABEL_KEYS[signal];
  return (
    <span
      className="px-3 py-1 rounded-full text-sm font-bold"
      style={{ backgroundColor: `${color}20`, color, border: `1px solid ${color}40` }}
    >
      {key ? t(key) : signal}
    </span>
  );
}

function ScoreBar({ score, label }: { score: number; label: string }) {
  const pct = ((score + 1) / 2) * 100; // -1..1 → 0..100
  const color = score > 0.2 ? "#10b981" : score < -0.2 ? "#ef4444" : "#f59e0b";

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-400 w-20 text-right">{label}</span>
      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden relative">
        <div className="absolute left-1/2 w-px h-full bg-slate-600" />
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${Math.abs(score) * 50}%`,
            marginLeft: score >= 0 ? "50%" : `${50 - Math.abs(score) * 50}%`,
            backgroundColor: color,
            boxShadow: `0 0 8px ${color}40`,
          }}
        />
      </div>
      <span className="text-xs font-mono w-12 text-right" style={{ color }}>
        {score > 0 ? "+" : ""}{score.toFixed(2)}
      </span>
    </div>
  );
}

export default function SignalsPage() {
  const { t } = useTranslation();
  const [symbol, setSymbol] = useState("BTC/USDT");
  const { data: signal, isLoading: signalLoading, error: signalError } = useSignalAnalysis(symbol);
  const { data: regime, isLoading: regimeLoading } = useMarketRegime();
  const { data: anomalies } = useAnomalies();
  const { data: scorecard } = useScorecard(symbol);

  const symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "BNB/USDT", "ADA/USDT"];

  // Radar data from agent scores
  const radarData = signal?.agents?.map((a) => ({
    agent: a.agent.charAt(0).toUpperCase() + a.agent.slice(1),
    score: ((a.score + 1) / 2) * 100, // normalize to 0-100
    confidence: a.confidence * 100,
  })) || [];

  // Agent comparison bars
  const agentBars = signal?.agents?.map((a) => ({
    name: a.agent.charAt(0).toUpperCase() + a.agent.slice(1),
    score: a.score,
    confidence: a.confidence,
  })) || [];

  const anomalyData = anomalies as Record<string, number> | undefined;
  const totalAnomalies = anomalyData?.total_anomalies ?? 0;

  const regimeData = regime as Record<string, unknown> | undefined;
  const scorecardData = scorecard as Record<string, number> | undefined;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{t("signalsPage.title")}</h1>
          <p className="text-slate-400 text-sm mt-1">{t("signalsPage.subtitle")}</p>
        </div>
        <div className="flex gap-2">
          {symbols.map((s) => (
            <button
              key={s}
              onClick={() => setSymbol(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                symbol === s ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400 hover:text-white"
              }`}
            >
              {s.split("/")[0]}
            </button>
          ))}
        </div>
      </div>

      {/* Composite Signal + Regime */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Main Signal */}
        <div className="md:col-span-2 bg-slate-900 rounded-xl border border-slate-700 p-6">
          {signalLoading ? (
            <div className="flex items-center justify-center h-40">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400" />
            </div>
          ) : signalError ? (
            <div className="text-center text-red-400 py-8">{t("signalsPage.failedToLoad")}</div>
          ) : signal ? (
            <div>
              <div className="flex items-center justify-between mb-6">
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">{t("signalsPage.compositeSignal")}</p>
                  <div className="flex items-center gap-4">
                    <SignalBadge signal={signal.overall_signal} />
                    <span className="text-3xl font-bold font-mono" style={{ color: SIGNAL_COLORS[signal.overall_signal] || "#64748b" }}>
                      {signal.overall_score > 0 ? "+" : ""}{signal.overall_score.toFixed(3)}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs text-slate-400">{t("signalsPage.confidence")}</p>
                  <p className="text-2xl font-bold text-white">{(signal.confidence * 100).toFixed(0)}%</p>
                </div>
              </div>

              {/* Agent Scores */}
              <div className="space-y-3 mt-4">
                {signal.agents?.map((a) => (
                  <ScoreBar key={a.agent} score={a.score} label={a.agent.charAt(0).toUpperCase() + a.agent.slice(1)} />
                ))}
              </div>

              {/* Key Drivers */}
              {signal.key_drivers?.length > 0 && (
                <div className="mt-5 pt-4 border-t border-slate-800">
                  <p className="text-xs text-slate-400 uppercase mb-2">{t("signalsPage.keyDrivers")}</p>
                  <div className="flex flex-wrap gap-2">
                    {signal.key_drivers.map((d, i) => (
                      <span key={i} className="px-2 py-1 bg-slate-800 rounded text-xs text-slate-300">{d}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Risk Factors */}
              {signal.risk_factors?.length > 0 && signal.risk_factors[0] !== "No significant risks detected" && (
                <div className="mt-4">
                  <p className="text-xs text-red-400 uppercase mb-2">{t("signalsPage.riskFactors")}</p>
                  {signal.risk_factors.map((r, i) => (
                    <p key={i} className="text-xs text-red-300/70 mt-1">- {r}</p>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Right column: Regime + Anomalies */}
        <div className="space-y-4">
          {/* Market Regime */}
          <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <p className="text-xs text-slate-400 uppercase tracking-wider mb-3">{t("signalsPage.marketRegime")}</p>
            {regimeLoading ? (
              <div className="h-12 bg-slate-800 rounded animate-pulse" />
            ) : regime ? (
              <div>
                <div className="flex items-center gap-3">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: REGIME_COLORS[String(regimeData?.regime ?? "unknown")] || "#64748b" }}
                  />
                  <span className="text-lg font-bold text-white capitalize">
                    {String(String(regimeData?.regime ?? "unknown") || "unknown").replace(/_/g, " ")}
                  </span>
                </div>
                <p className="text-sm text-slate-400 mt-2">
                  {t("signalsPage.regimeConfidence")}: {(Number(regimeData?.confidence ?? 0) * 100).toFixed(0)}%
                </p>
                {Array.isArray(regimeData?.reasons) && (
                  <div className="mt-3 space-y-1">
                    {(regimeData.reasons as string[]).map((r: string, i: number) => (
                      <p key={i} className="text-xs text-slate-500">- {r}</p>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-slate-500 text-sm">{t("signalsPage.noData")}</p>
            )}
          </div>

          {/* Anomalies Summary */}
          <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <p className="text-xs text-slate-400 uppercase tracking-wider mb-3">{t("signalsPage.anomalyDetection")}</p>
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg font-bold ${
                Number(totalAnomalies) > 0 ? "bg-red-500/20 text-red-400" : "bg-emerald-500/20 text-emerald-400"
              }`}>
                {String(totalAnomalies)}
              </div>
              <div>
                <p className="text-sm text-white">
                  {Number(totalAnomalies) > 0 ? t("signalsPage.anomaliesDetected") : t("signalsPage.allClear")}
                </p>
                <p className="text-xs text-slate-500">
                  {Number(totalAnomalies) > 0 ? t("signalsPage.checkSignals") : t("signalsPage.allMetricsNormal")}
                </p>
              </div>
            </div>
          </div>

          {/* Scorecard Preview */}
          {scorecardData && scorecardData.total_signals > 0 && (
            <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
              <p className="text-xs text-slate-400 uppercase tracking-wider mb-3">{t("signalsPage.scorecard")}</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-slate-500">{t("signalsPage.winRate")}</p>
                  <p className="text-lg font-bold text-white">
                    {(scorecardData.win_rate * 100).toFixed(1)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">{t("signalsPage.avgReturn")}</p>
                  <p className={`text-lg font-bold ${scorecardData.avg_return_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {scorecardData.avg_return_pct > 0 ? "+" : ""}
                    {scorecardData.avg_return_pct?.toFixed(2)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">{t("signalsPage.signalsCount")}</p>
                  <p className="text-lg font-bold text-white">{scorecardData.total_signals}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">{t("signalsPage.sharpe")}</p>
                  <p className="text-lg font-bold text-blue-400">{scorecardData.signal_sharpe?.toFixed(2)}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Agent Radar Chart */}
      {radarData.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <h2 className="text-sm font-semibold text-white mb-4">{t("signalsPage.agentRadar")}</h2>
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#334155" />
                <PolarAngleAxis dataKey="agent" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: "#64748b", fontSize: 10 }} />
                <Radar name="Score" dataKey="score" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
                <Radar name="Confidence" dataKey="confidence" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.15} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#fff", fontSize: 12 }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <h2 className="text-sm font-semibold text-white mb-4">{t("signalsPage.agentScores")}</h2>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={agentBars} layout="vertical" margin={{ left: 20 }}>
                <XAxis type="number" domain={[-1, 1]} tickFormatter={(v) => v.toFixed(1)} stroke="#64748b" fontSize={11} />
                <YAxis type="category" dataKey="name" stroke="#94a3b8" fontSize={12} width={80} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#fff", fontSize: 12 }}
                  formatter={(v) => [Number(v).toFixed(3), "Score"]}
                />
                <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                  {agentBars.map((entry, index) => (
                    <Cell key={index} fill={entry.score >= 0.2 ? "#10b981" : entry.score <= -0.2 ? "#ef4444" : "#f59e0b"} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Agent Detail Cards */}
      {signal?.agents && signal.agents.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {signal.agents.map((a) => (
            <div key={a.agent} className="bg-slate-900 rounded-xl border border-slate-700 p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-white capitalize">{a.agent} Agent</h3>
                <span className={`text-xs font-mono px-2 py-0.5 rounded ${
                  a.score > 0.1 ? "bg-emerald-500/20 text-emerald-400" :
                  a.score < -0.1 ? "bg-red-500/20 text-red-400" :
                  "bg-amber-500/20 text-amber-400"
                }`}>
                  {a.score > 0 ? "+" : ""}{a.score.toFixed(3)}
                </span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">{a.reasoning}</p>
              <div className="flex items-center gap-4 mt-3 pt-3 border-t border-slate-800">
                <span className="text-xs text-slate-500">Signal: <span className="text-slate-300">{a.signal}</span></span>
                <span className="text-xs text-slate-500">Confidence: <span className="text-slate-300">{(a.confidence * 100).toFixed(0)}%</span></span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
