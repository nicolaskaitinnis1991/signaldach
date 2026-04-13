"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { clsx } from "clsx";
import { BACKEND_URL } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChecklistItem {
  id: string;
  requirement: string;
  description: string;
  status: string;
  deadline: string | null;
  jurisdictions: string[];
  severity: string;
  reference_url: string;
  action: string;
}

interface Category {
  name: string;
  items: ChecklistItem[];
}

interface ComplianceData {
  business_type: string;
  jurisdiction: string;
  framework: string;
  last_updated: string;
  overall_status: string;
  categories: Category[];
  recent_changes: Array<{
    date: string;
    title: string;
    impact: string;
    severity: string;
  }>;
  costs_estimate: Record<string, string>;
}

interface TimelineDeadline {
  date: string;
  business_type: string;
  requirement_id: string | null;
  requirement: string;
  description: string;
  severity: string;
  jurisdictions: string[];
  action: string | null;
}

interface TimelineData {
  total_deadlines: number;
  deadlines: TimelineDeadline[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BUSINESS_TYPES = [
  { key: "casp", labelKey: "compliance.casp", descKey: "compliance.caspDesc" },
  { key: "fund", labelKey: "compliance.fund", descKey: "compliance.fundDesc" },
  { key: "issuer", labelKey: "compliance.issuer", descKey: "compliance.issuerDesc" },
  { key: "custody", labelKey: "compliance.custody", descKey: "compliance.custodyDesc" },
] as const;

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-500/20 text-red-400 border-red-500/30",
  high: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  medium: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  low: "bg-slate-700/50 text-slate-400 border-slate-600",
};

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-amber-500",
  medium: "bg-blue-500",
  low: "bg-slate-500",
};

const JURISDICTION_COLORS: Record<string, string> = {
  DE: "bg-yellow-900/50 text-yellow-300 border-yellow-700",
  CH: "bg-red-900/50 text-red-300 border-red-700",
  EU: "bg-blue-900/50 text-blue-300 border-blue-700",
  AT: "bg-emerald-900/50 text-emerald-300 border-emerald-700",
};

const LS_KEY = "signaldach-compliance-completed";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CompliancePage() {
  const { t } = useTranslation();
  const [businessType, setBusinessType] = useState("casp");
  const [data, setData] = useState<ComplianceData | null>(null);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [completedItems, setCompletedItems] = useState<Set<string>>(new Set());

  // Load completed state from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(LS_KEY);
      if (stored) {
        setCompletedItems(new Set(JSON.parse(stored)));
      }
    } catch {
      // ignore
    }
  }, []);

  // Save completed state to localStorage
  const persistCompleted = useCallback((items: Set<string>) => {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify([...items]));
    } catch {
      // ignore
    }
  }, []);

  const toggleCompleted = useCallback(
    (id: string) => {
      setCompletedItems((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        persistCompleted(next);
        return next;
      });
    },
    [persistCompleted]
  );

  const toggleCategory = useCallback((name: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  // Fetch compliance data
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [compRes, timeRes] = await Promise.all([
        fetch(`${BACKEND_URL}/compliance/check?business_type=${businessType}`),
        fetch(`${BACKEND_URL}/compliance/timeline`),
      ]);
      const compData = await compRes.json();
      const timeData = await timeRes.json();
      setData(compData);
      setTimeline(timeData);
      // Expand all categories by default
      if (compData.categories) {
        setExpandedCategories(new Set(compData.categories.map((c: Category) => c.name)));
      }
    } catch {
      setData(null);
      setTimeline(null);
    } finally {
      setLoading(false);
    }
  }, [businessType]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Stats
  const stats = useMemo(() => {
    if (!data) return { total: 0, completed: 0, critical: 0, upcoming: 0 };
    let total = 0;
    let critical = 0;
    data.categories.forEach((cat) => {
      cat.items.forEach((item) => {
        total++;
        if (item.severity === "critical") critical++;
      });
    });
    const completed = data.categories.reduce(
      (acc, cat) => acc + cat.items.filter((i) => completedItems.has(i.id)).length,
      0
    );

    // Count upcoming deadlines (within 6 months)
    const sixMonthsFromNow = new Date();
    sixMonthsFromNow.setMonth(sixMonthsFromNow.getMonth() + 6);
    const upcoming =
      timeline?.deadlines.filter(
        (d) => new Date(d.date) <= sixMonthsFromNow && new Date(d.date) >= new Date()
      ).length ?? 0;

    return { total, completed, critical, upcoming };
  }, [data, completedItems, timeline]);

  const completionPercent = stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0;

  // Upcoming deadlines (next 12 months, filtered to current business type or "all")
  const upcomingDeadlines = useMemo(() => {
    if (!timeline) return [];
    const now = new Date();
    const oneYear = new Date();
    oneYear.setFullYear(oneYear.getFullYear() + 1);
    return timeline.deadlines
      .filter(
        (d) =>
          new Date(d.date) >= now &&
          new Date(d.date) <= oneYear &&
          (d.business_type === businessType || d.business_type === "all")
      )
      .slice(0, 10);
  }, [timeline, businessType]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <div className="text-slate-500 text-center">
          <div className="w-8 h-8 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin mx-auto mb-4" />
          <p>{t("compliance.loadingCompliance")}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-32 text-slate-500">
        <p className="text-lg mb-2">{t("compliance.failedToLoad")}</p>
        <p className="text-sm">{t("compliance.failedToLoadDesc")}</p>
      </div>
    );
  }

  return (
    <>
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">{t("compliance.title")}</h2>
        <p className="text-sm text-slate-400 mt-1">
          {t("compliance.subtitle")}
          Framework: <span className="text-slate-300 font-medium">{data.framework}</span>
        </p>
      </div>

      {/* Business type selector */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        {BUSINESS_TYPES.map((bt) => (
          <button
            key={bt.key}
            onClick={() => setBusinessType(bt.key)}
            className={clsx(
              "rounded-xl border p-4 text-left transition-all duration-200",
              businessType === bt.key
                ? "bg-blue-600/20 border-blue-500 ring-1 ring-blue-500/50"
                : "bg-slate-900 border-slate-700 hover:border-slate-600"
            )}
          >
            <p
              className={clsx(
                "font-bold text-sm",
                businessType === bt.key ? "text-blue-400" : "text-white"
              )}
            >
              {t(bt.labelKey)}
            </p>
            <p className="text-[10px] text-slate-400 mt-0.5">{t(bt.descKey)}</p>
          </button>
        ))}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-slate-400">{t("compliance.completion")}</p>
            <span className="text-xs font-bold text-blue-400">{completionPercent}%</span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${completionPercent}%` }}
            />
          </div>
          <p className="text-xs text-slate-500 mt-2">
            {stats.completed}/{stats.total} items
          </p>
        </div>
        <div className="bg-slate-900 rounded-xl border border-red-900/50 p-4">
          <p className="text-2xl font-bold text-red-400">{stats.critical}</p>
          <p className="text-xs text-slate-400">{t("compliance.criticalItems")}</p>
        </div>
        <div className="bg-slate-900 rounded-xl border border-amber-900/50 p-4">
          <p className="text-2xl font-bold text-amber-400">{stats.upcoming}</p>
          <p className="text-xs text-slate-400">{t("compliance.upcomingDeadlines")}</p>
        </div>
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
          <p className="text-2xl font-bold text-white">{data.categories.length}</p>
          <p className="text-xs text-slate-400">{t("compliance.categories")}</p>
        </div>
      </div>

      {/* Checklist by category */}
      <div className="space-y-4 mb-10">
        {data.categories.map((cat) => {
          const isExpanded = expandedCategories.has(cat.name);
          const catCompleted = cat.items.filter((i) => completedItems.has(i.id)).length;
          const catPercent = cat.items.length > 0 ? Math.round((catCompleted / cat.items.length) * 100) : 0;

          return (
            <div key={cat.name} className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
              <button
                onClick={() => toggleCategory(cat.name)}
                className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-800/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <svg
                    className={clsx("w-4 h-4 text-slate-400 transition-transform", isExpanded && "rotate-90")}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                  </svg>
                  <h3 className="font-semibold text-white text-sm">{cat.name}</h3>
                  <span className="text-xs text-slate-500">({cat.items.length} items)</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-400">{catPercent}%</span>
                  <div className="w-20 bg-slate-800 rounded-full h-1.5">
                    <div
                      className="bg-blue-500 h-1.5 rounded-full transition-all duration-500"
                      style={{ width: `${catPercent}%` }}
                    />
                  </div>
                </div>
              </button>

              {isExpanded && (
                <div className="border-t border-slate-800 divide-y divide-slate-800/50">
                  {cat.items.map((item) => {
                    const isCompleted = completedItems.has(item.id);

                    return (
                      <div
                        key={item.id}
                        className={clsx(
                          "px-5 py-4 transition-colors",
                          isCompleted ? "bg-slate-900/50 opacity-60" : "hover:bg-slate-800/30"
                        )}
                      >
                        <div className="flex items-start gap-3">
                          {/* Checkbox */}
                          <button
                            onClick={() => toggleCompleted(item.id)}
                            className={clsx(
                              "mt-0.5 w-5 h-5 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors",
                              isCompleted
                                ? "bg-blue-600 border-blue-600"
                                : "border-slate-600 hover:border-slate-500"
                            )}
                          >
                            {isCompleted && (
                              <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                              </svg>
                            )}
                          </button>

                          <div className="flex-1 min-w-0">
                            {/* Title row */}
                            <div className="flex items-center gap-2 flex-wrap mb-1">
                              <h4
                                className={clsx(
                                  "font-medium text-sm",
                                  isCompleted ? "line-through text-slate-500" : "text-white"
                                )}
                              >
                                {item.requirement}
                              </h4>
                              {/* Severity badge */}
                              <span
                                className={clsx(
                                  "px-1.5 py-0.5 rounded text-[10px] font-bold border",
                                  SEVERITY_COLORS[item.severity] ?? SEVERITY_COLORS.low
                                )}
                              >
                                {item.severity.toUpperCase()}
                              </span>
                              {/* Jurisdiction badges */}
                              {item.jurisdictions.map((j) => (
                                <span
                                  key={j}
                                  className={clsx(
                                    "px-1.5 py-0.5 rounded text-[10px] font-bold border",
                                    JURISDICTION_COLORS[j] ?? "bg-slate-700 text-slate-300 border-slate-600"
                                  )}
                                >
                                  {j}
                                </span>
                              ))}
                            </div>

                            {/* Description */}
                            <p className="text-xs text-slate-400 mb-2">{item.description}</p>

                            {/* Action + deadline */}
                            <div className="flex items-start justify-between gap-4 flex-wrap">
                              <div className="flex-1 min-w-0">
                                <p className="text-xs text-slate-300">
                                  <span className="text-slate-500 font-medium">{t("compliance.action")}: </span>
                                  {item.action}
                                </p>
                              </div>
                              {item.deadline && (
                                <div className="flex-shrink-0">
                                  <span
                                    className={clsx(
                                      "text-[10px] font-medium px-2 py-1 rounded",
                                      new Date(item.deadline) < new Date()
                                        ? "bg-red-500/20 text-red-400"
                                        : new Date(item.deadline) < new Date(Date.now() + 90 * 86400000)
                                          ? "bg-amber-500/20 text-amber-400"
                                          : "bg-slate-800 text-slate-400"
                                    )}
                                  >
                                    {t("compliance.deadline")}: {item.deadline}
                                  </span>
                                </div>
                              )}
                            </div>

                            {/* Reference link */}
                            {item.reference_url && (
                              <a
                                href={item.reference_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-block mt-2 text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
                              >
                                {t("compliance.viewSource")}
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Upcoming Deadlines */}
      {upcomingDeadlines.length > 0 && (
        <div className="mb-10">
          <h3 className="text-lg font-bold text-white mb-4">{t("compliance.upcomingDeadlines")}</h3>
          <div className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
            <div className="divide-y divide-slate-800">
              {upcomingDeadlines.map((d, i) => (
                <div key={i} className="flex items-center gap-4 px-5 py-3">
                  <div
                    className={clsx(
                      "w-2.5 h-2.5 rounded-full flex-shrink-0",
                      SEVERITY_DOT[d.severity] ?? SEVERITY_DOT.low
                    )}
                  />
                  <div className="flex-shrink-0 w-24">
                    <span
                      className={clsx(
                        "text-xs font-mono font-medium",
                        new Date(d.date) < new Date(Date.now() + 90 * 86400000)
                          ? "text-red-400"
                          : "text-slate-400"
                      )}
                    >
                      {d.date}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white truncate">{d.requirement}</p>
                    <p className="text-[10px] text-slate-500 truncate">{d.description}</p>
                  </div>
                  <span
                    className={clsx(
                      "px-1.5 py-0.5 rounded text-[10px] font-bold border flex-shrink-0",
                      SEVERITY_COLORS[d.severity] ?? SEVERITY_COLORS.low
                    )}
                  >
                    {d.severity.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Recent regulatory changes */}
      <div className="mb-10">
        <h3 className="text-lg font-bold text-white mb-4">{t("compliance.recentChanges")}</h3>
        <div className="space-y-3">
          {data.recent_changes.map((change, i) => (
            <div
              key={i}
              className={clsx(
                "bg-slate-900 rounded-xl border p-4",
                change.severity === "critical"
                  ? "border-red-900/50"
                  : change.severity === "high"
                    ? "border-amber-900/50"
                    : "border-slate-700"
              )}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-mono text-slate-500">{change.date}</span>
                <span
                  className={clsx(
                    "px-1.5 py-0.5 rounded text-[10px] font-bold border",
                    SEVERITY_COLORS[change.severity] ?? SEVERITY_COLORS.low
                  )}
                >
                  {change.severity.toUpperCase()}
                </span>
              </div>
              <h4 className="font-semibold text-white text-sm mb-1">{change.title}</h4>
              <p className="text-xs text-slate-400">{change.impact}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Cost estimates */}
      <div className="mb-10">
        <h3 className="text-lg font-bold text-white mb-4">{t("compliance.estimatedCosts")}</h3>
        <div className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
          <div className="divide-y divide-slate-800">
            {Object.entries(data.costs_estimate).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between px-5 py-3">
                <span className="text-sm text-slate-300 capitalize">
                  {key.replace(/_/g, " ")}
                </span>
                <span className="text-sm font-mono font-medium text-white">{value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer note */}
      <div className="text-center pb-8">
        <p className="text-[10px] text-slate-600">
          Last updated: {data.last_updated} | This checklist is for informational purposes only and does
          not constitute legal advice. Consult qualified legal counsel for compliance decisions.
        </p>
      </div>
    </>
  );
}
