"use client";

import { useCallback, useEffect, useState } from "react";
import { clsx } from "clsx";
import { BACKEND_URL, timeAgo } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Warning {
  id: string;
  title: string;
  regulator: string;
  severity: string;
  entities_mentioned: string[];
  date: string | null;
  url: string | null;
  type: string;
  summary: string | null;
}

interface WarningsResponse {
  total_warnings: number;
  total_in_database: number;
  by_regulator: Record<string, number>;
  by_severity: Record<string, number>;
  warnings: Warning[];
}

interface EntityCheckResult {
  entity: string;
  flagged: boolean;
  match_count: number;
  risk_level: string;
  message: string;
  matches: Warning[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-500/20 text-red-400 border-red-500/30",
  high: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  medium: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  low: "bg-slate-700/50 text-slate-400 border-slate-600",
};

const REGULATOR_COLORS: Record<string, string> = {
  BaFin: "bg-yellow-900/50 text-yellow-300 border-yellow-700",
  FINMA: "bg-red-900/50 text-red-300 border-red-700",
  FCA: "bg-purple-900/50 text-purple-300 border-purple-700",
  ESMA: "bg-blue-900/50 text-blue-300 border-blue-700",
  SEC: "bg-emerald-900/50 text-emerald-300 border-emerald-700",
  FMA: "bg-teal-900/50 text-teal-300 border-teal-700",
  Unknown: "bg-slate-700/50 text-slate-400 border-slate-600",
};

const TYPE_LABEL_KEYS: Record<string, string> = {
  unauthorized_service: "scamMonitor.unauthorizedService",
  fraud: "scamMonitor.fraud",
  suspension: "scamMonitor.suspension",
  investigation: "scamMonitor.investigation",
  general_warning: "scamMonitor.generalWarning",
};

const RISK_COLORS: Record<string, string> = {
  critical: "text-red-400 bg-red-500/20 border-red-500/30",
  high: "text-amber-400 bg-amber-500/20 border-amber-500/30",
  medium: "text-blue-400 bg-blue-500/20 border-blue-500/30",
  low: "text-slate-400 bg-slate-700/50 border-slate-600",
  none: "text-green-400 bg-green-500/20 border-green-500/30",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ScamMonitorPage() {
  const { t } = useTranslation();
  const [data, setData] = useState<WarningsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterRegulator, setFilterRegulator] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string | null>(null);

  // Entity check
  const [entityQuery, setEntityQuery] = useState("");
  const [entityResult, setEntityResult] = useState<EntityCheckResult | null>(null);
  const [entityLoading, setEntityLoading] = useState(false);

  const loadWarnings = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterRegulator) params.set("regulator", filterRegulator);
      if (filterSeverity) params.set("severity", filterSeverity);
      const res = await fetch(`${BACKEND_URL}/scam-monitor/warnings?${params}`);
      const json = await res.json();
      setData(json);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [filterRegulator, filterSeverity]);

  useEffect(() => {
    loadWarnings();
    const interval = setInterval(loadWarnings, 60000);
    return () => clearInterval(interval);
  }, [loadWarnings]);

  const checkEntity = useCallback(async () => {
    if (!entityQuery.trim()) return;
    setEntityLoading(true);
    setEntityResult(null);
    try {
      const res = await fetch(
        `${BACKEND_URL}/scam-monitor/check?entity=${encodeURIComponent(entityQuery.trim())}`
      );
      const json = await res.json();
      setEntityResult(json);
    } catch {
      setEntityResult(null);
    } finally {
      setEntityLoading(false);
    }
  }, [entityQuery]);

  const allRegulators = data ? Object.keys(data.by_regulator) : [];
  const allSeverities = ["critical", "high", "medium", "low"];

  return (
    <>
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">{t("scamMonitor.title")}</h2>
        <p className="text-sm text-slate-400 mt-1">
          {t("scamMonitor.subtitle")}
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
          <p className="text-2xl font-bold text-white">{data?.total_warnings ?? 0}</p>
          <p className="text-xs text-slate-400">{t("scamMonitor.totalWarnings")}</p>
        </div>
        {/* Regulator breakdown */}
        {data &&
          Object.entries(data.by_regulator)
            .sort(([, a], [, b]) => b - a)
            .slice(0, 3)
            .map(([reg, count]) => (
              <div
                key={reg}
                className={clsx(
                  "bg-slate-900 rounded-xl border p-4",
                  reg === "BaFin"
                    ? "border-yellow-700/50"
                    : reg === "FINMA"
                      ? "border-red-700/50"
                      : "border-slate-700"
                )}
              >
                <p className="text-2xl font-bold text-white">{count}</p>
                <p className="text-xs text-slate-400">{reg}</p>
              </div>
            ))}
      </div>

      {/* Severity breakdown bar */}
      {data && data.total_warnings > 0 && (
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-4 mb-8">
          <p className="text-xs text-slate-400 mb-2">{t("signalsPage.severityDistribution")}</p>
          <div className="flex rounded-full overflow-hidden h-3">
            {allSeverities.map((sev) => {
              const count = data.by_severity[sev] ?? 0;
              if (count === 0) return null;
              const pct = (count / data.total_warnings) * 100;
              const colors: Record<string, string> = {
                critical: "bg-red-500",
                high: "bg-amber-500",
                medium: "bg-blue-500",
                low: "bg-slate-600",
              };
              return (
                <div
                  key={sev}
                  className={clsx(colors[sev])}
                  style={{ width: `${pct}%` }}
                  title={`${sev}: ${count}`}
                />
              );
            })}
          </div>
          <div className="flex gap-4 mt-2">
            {allSeverities.map((sev) => {
              const count = data.by_severity[sev] ?? 0;
              if (count === 0) return null;
              return (
                <span key={sev} className="text-[10px] text-slate-400">
                  <span
                    className={clsx(
                      "inline-block w-2 h-2 rounded-full mr-1",
                      sev === "critical"
                        ? "bg-red-500"
                        : sev === "high"
                          ? "bg-amber-500"
                          : sev === "medium"
                            ? "bg-blue-500"
                            : "bg-slate-600"
                    )}
                  />
                  {sev}: {count}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Entity check */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-5 mb-8">
        <h3 className="font-semibold text-white text-sm mb-3">{t("scamMonitor.checkCompany")}</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={entityQuery}
            onChange={(e) => setEntityQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && checkEntity()}
            placeholder={t("scamMonitor.placeholder")}
            className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50"
          />
          <button
            onClick={checkEntity}
            disabled={entityLoading || !entityQuery.trim()}
            className={clsx(
              "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              entityLoading || !entityQuery.trim()
                ? "bg-slate-800 text-slate-500 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700"
            )}
          >
            {entityLoading ? t("scamMonitor.checking") : t("scamMonitor.check")}
          </button>
        </div>

        {entityResult && (
          <div className="mt-4">
            <div
              className={clsx(
                "rounded-lg border p-4",
                RISK_COLORS[entityResult.risk_level] ?? RISK_COLORS.none
              )}
            >
              <div className="flex items-center gap-2 mb-1">
                {entityResult.flagged ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                )}
                <span className="font-bold text-sm">
                  {entityResult.flagged ? "FLAGGED" : "CLEAR"} — {entityResult.entity}
                </span>
              </div>
              <p className="text-xs opacity-80">{entityResult.message}</p>
              {entityResult.flagged && (
                <p className="text-xs mt-1 opacity-60">
                  Risk level: {entityResult.risk_level.toUpperCase()} | {entityResult.match_count} match(es)
                </p>
              )}
            </div>

            {/* Show matching warnings */}
            {entityResult.matches.length > 0 && (
              <div className="mt-3 space-y-2">
                {entityResult.matches.slice(0, 5).map((m) => (
                  <div key={m.id} className="bg-slate-800 rounded-lg border border-slate-700 p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={clsx(
                          "px-1.5 py-0.5 rounded text-[10px] font-bold border",
                          REGULATOR_COLORS[m.regulator] ?? REGULATOR_COLORS.Unknown
                        )}
                      >
                        {m.regulator}
                      </span>
                      <span
                        className={clsx(
                          "px-1.5 py-0.5 rounded text-[10px] font-bold border",
                          SEVERITY_COLORS[m.severity] ?? SEVERITY_COLORS.low
                        )}
                      >
                        {m.severity.toUpperCase()}
                      </span>
                      <span className="text-[10px] text-slate-500">{timeAgo(m.date)}</span>
                    </div>
                    <p className="text-xs text-white">{m.title}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-6">
        <span className="text-xs text-slate-500 self-center mr-2">{t("scamMonitor.regulator")}:</span>
        <button
          onClick={() => setFilterRegulator(null)}
          className={clsx(
            "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
            !filterRegulator
              ? "bg-slate-700 text-white"
              : "bg-slate-900 border border-slate-700 text-slate-300 hover:bg-slate-800"
          )}
        >
          All
        </button>
        {allRegulators.map((reg) => (
          <button
            key={reg}
            onClick={() => setFilterRegulator(filterRegulator === reg ? null : reg)}
            className={clsx(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border",
              filterRegulator === reg
                ? (REGULATOR_COLORS[reg] ?? REGULATOR_COLORS.Unknown)
                : "bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800"
            )}
          >
            {reg} ({data?.by_regulator[reg] ?? 0})
          </button>
        ))}

        <span className="text-xs text-slate-500 self-center ml-4 mr-2">{t("scamMonitor.severity")}:</span>
        <button
          onClick={() => setFilterSeverity(null)}
          className={clsx(
            "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
            !filterSeverity
              ? "bg-slate-700 text-white"
              : "bg-slate-900 border border-slate-700 text-slate-300 hover:bg-slate-800"
          )}
        >
          All
        </button>
        {allSeverities.map((sev) => (
          <button
            key={sev}
            onClick={() => setFilterSeverity(filterSeverity === sev ? null : sev)}
            className={clsx(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border",
              filterSeverity === sev
                ? (SEVERITY_COLORS[sev] ?? SEVERITY_COLORS.low)
                : "bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800"
            )}
          >
            {sev}
          </button>
        ))}
      </div>

      {/* Warnings list */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="text-slate-500 text-center">
            <div className="w-8 h-8 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin mx-auto mb-4" />
            <p>{t("scamMonitor.loadingWarnings")}</p>
          </div>
        </div>
      ) : !data || data.total_warnings === 0 ? (
        <div className="text-center py-20 text-slate-500">
          <svg className="w-12 h-12 mx-auto mb-4 text-slate-600" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-lg mb-2">{t("scamMonitor.noWarnings")}</p>
          <p className="text-sm">
            {t("scamMonitor.noWarningsDesc")}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.warnings.map((w) => (
            <a
              key={w.id}
              href={w.url ?? "#"}
              target="_blank"
              rel="noopener noreferrer"
              className={clsx(
                "block bg-slate-900 rounded-xl border p-5 hover:border-slate-600 transition-all duration-200",
                w.severity === "critical"
                  ? "border-l-4 border-l-red-500 border-r-slate-700 border-t-slate-700 border-b-slate-700"
                  : w.severity === "high"
                    ? "border-l-4 border-l-amber-500 border-r-slate-700 border-t-slate-700 border-b-slate-700"
                    : "border-slate-700"
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    {/* Regulator badge */}
                    <span
                      className={clsx(
                        "px-2 py-0.5 rounded-full text-[10px] font-bold border",
                        REGULATOR_COLORS[w.regulator] ?? REGULATOR_COLORS.Unknown
                      )}
                    >
                      {w.regulator}
                    </span>
                    {/* Severity badge */}
                    <span
                      className={clsx(
                        "px-2 py-0.5 rounded-full text-[10px] font-bold border",
                        SEVERITY_COLORS[w.severity] ?? SEVERITY_COLORS.low
                      )}
                    >
                      {w.severity.toUpperCase()}
                    </span>
                    {/* Type badge */}
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
                      {TYPE_LABEL_KEYS[w.type] ? t(TYPE_LABEL_KEYS[w.type]) : w.type}
                    </span>
                    {/* Date */}
                    <span className="text-[10px] text-slate-500">{timeAgo(w.date)}</span>
                  </div>

                  <h3 className="font-semibold text-white text-sm leading-snug mb-1">
                    {w.title}
                  </h3>

                  {w.summary && (
                    <p className="text-xs text-slate-400 line-clamp-2 mb-2">{w.summary}</p>
                  )}

                  {/* Entities mentioned */}
                  {w.entities_mentioned.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-[10px] text-slate-500">Entities:</span>
                      {w.entities_mentioned.map((e, i) => (
                        <span
                          key={i}
                          className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-950/50 text-red-300 border border-red-900/50"
                        >
                          {e}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Arrow icon */}
                <div className="flex-shrink-0 text-slate-600">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                  </svg>
                </div>
              </div>
            </a>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className="text-center py-8">
        <p className="text-[10px] text-slate-600">
          Warnings are extracted from regulatory news items. Always verify with official regulator websites.
        </p>
      </div>
    </>
  );
}
