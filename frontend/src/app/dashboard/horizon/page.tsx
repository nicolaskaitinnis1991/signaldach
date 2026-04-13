"use client";

import { useCallback, useEffect, useState } from "react";
import { clsx } from "clsx";
import { BACKEND_URL } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HorizonItem {
  id: string;
  title: string;
  summary: string;
  url: string;
  original_relevance: number;
  personal_relevance: number;
  relevance_reason: string;
  category: "directly_affects_you" | "monitor" | "low_relevance";
  recommended_action: string;
  deadline: string | null;
  source: string;
  date: string;
  urgency: string;
  tags: string[];
}

interface HorizonScan {
  business_type: string;
  jurisdictions: string[];
  scan_date: string;
  summary: {
    critical: number;
    monitor: number;
    low_relevance: number;
    total_scanned: number;
  };
  items: HorizonItem[];
}

interface BusinessType {
  id: string;
  name: string;
  description: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BUSINESS_TYPES: (BusinessType & { nameKey: string; descKey: string })[] = [
  { id: "fund", name: "Fund / Asset Manager", nameKey: "horizon.fund", description: "Investment funds, AIFMs, portfolio management", descKey: "horizon.fundDesc" },
  { id: "casp", name: "CASP", nameKey: "horizon.casp", description: "Exchanges, trading platforms, brokers", descKey: "horizon.caspDesc" },
  { id: "issuer", name: "Token Issuer", nameKey: "horizon.issuer", description: "ICO/STO issuers, stablecoins", descKey: "horizon.issuerDesc" },
  { id: "custody", name: "Custody Provider", nameKey: "horizon.custody", description: "Crypto custody, key management", descKey: "horizon.custodyDesc" },
];

const JURISDICTIONS = [
  { code: "DE", labelKey: "regulatory.germany", flag: "\uD83C\uDDE9\uD83C\uDDEA" },
  { code: "CH", labelKey: "regulatory.switzerland", flag: "\uD83C\uDDE8\uD83C\uDDED" },
  { code: "AT", labelKey: "horizon.austria", flag: "\uD83C\uDDE6\uD83C\uDDF9" },
  { code: "EU", labelKey: "regulatory.eu", flag: "\uD83C\uDDEA\uD83C\uDDFA" },
];

const CATEGORY_CONFIG = {
  directly_affects_you: {
    labelKey: "horizon.directlyAffectsYou",
    border: "border-red-500",
    bg: "bg-red-950/20",
    badge: "bg-red-900/50 text-red-400",
    icon: "!",
  },
  monitor: {
    labelKey: "horizon.monitor",
    border: "border-amber-500",
    bg: "bg-amber-950/20",
    badge: "bg-amber-900/50 text-amber-400",
    icon: "~",
  },
  low_relevance: {
    labelKey: "horizon.lowRelevance",
    border: "border-slate-600",
    bg: "bg-slate-900",
    badge: "bg-slate-800 text-slate-500",
    icon: "-",
  },
} as const;

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function HorizonPage() {
  const { t } = useTranslation();
  const [businessType, setBusinessType] = useState("fund");
  const [selectedJurisdictions, setSelectedJurisdictions] = useState<Set<string>>(new Set(["DE", "CH"]));
  const [days, setDays] = useState(30);
  const [activeView, setActiveView] = useState<"all" | "directly_affects_you" | "monitor" | "low_relevance">("all");

  const [scan, setScan] = useState<HorizonScan | null>(null);
  const [loading, setLoading] = useState(false);

  function toggleJurisdiction(code: string) {
    setSelectedJurisdictions((prev) => {
      const next = new Set(prev);
      if (next.has(code)) {
        if (next.size > 1) next.delete(code); // Keep at least one
      } else {
        next.add(code);
      }
      return next;
    });
  }

  const loadScan = useCallback(async () => {
    setLoading(true);
    try {
      const jurisdictions = Array.from(selectedJurisdictions).join(",");
      const res = await fetch(
        `${BACKEND_URL}/horizon/scan?business_type=${businessType}&jurisdictions=${jurisdictions}&days=${days}`
      );
      const data = await res.json();
      setScan(data);
    } catch {
      setScan(null);
    } finally {
      setLoading(false);
    }
  }, [businessType, selectedJurisdictions, days]);

  useEffect(() => {
    loadScan();
  }, [loadScan]);

  const filteredItems = scan?.items.filter(
    (item) => activeView === "all" || item.category === activeView
  ) ?? [];

  return (
    <>
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">
          {t("horizon.title")}
        </h2>
        <p className="text-sm text-slate-400 mt-1">
          {t("horizon.subtitle")}
        </p>
      </div>

      {/* Configuration */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-5 mb-6 space-y-4">
        {/* Business type */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-2">{t("horizon.businessType")}</label>
          <div className="flex gap-2 flex-wrap">
            {BUSINESS_TYPES.map((bt) => (
              <button
                key={bt.id}
                onClick={() => setBusinessType(bt.id)}
                className={clsx(
                  "px-4 py-2 rounded-lg text-xs font-semibold transition-colors border",
                  businessType === bt.id
                    ? "bg-blue-600 border-blue-500 text-white"
                    : "bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700"
                )}
                title={t(bt.descKey)}
              >
                {t(bt.nameKey)}
              </button>
            ))}
          </div>
        </div>

        {/* Jurisdictions */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-2">{t("horizon.jurisdictions")}</label>
          <div className="flex gap-2 flex-wrap">
            {JURISDICTIONS.map((j) => (
              <button
                key={j.code}
                onClick={() => toggleJurisdiction(j.code)}
                className={clsx(
                  "flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold transition-colors border",
                  selectedJurisdictions.has(j.code)
                    ? "bg-slate-700 border-slate-500 text-white"
                    : "bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-700"
                )}
              >
                <span>{j.flag}</span> {t(j.labelKey)}
              </button>
            ))}
          </div>
        </div>

        {/* Time period */}
        <div className="flex items-center gap-3">
          <label className="text-xs font-medium text-slate-400">{t("horizon.lookback")}:</label>
          {[7, 14, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={clsx(
                "px-3 py-1 rounded-lg text-xs font-medium transition-colors",
                days === d
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              )}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Summary stats */}
      {scan && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          <div
            className="bg-slate-900 rounded-xl border-2 border-red-700 p-4 cursor-pointer hover:bg-red-950/20 transition-colors"
            onClick={() => setActiveView("directly_affects_you")}
          >
            <p className="text-2xl font-bold text-red-400">{scan.summary.critical}</p>
            <p className="text-xs text-slate-400">{t("horizon.directlyAffectsYou")}</p>
          </div>
          <div
            className="bg-slate-900 rounded-xl border-2 border-amber-700 p-4 cursor-pointer hover:bg-amber-950/20 transition-colors"
            onClick={() => setActiveView("monitor")}
          >
            <p className="text-2xl font-bold text-amber-400">{scan.summary.monitor}</p>
            <p className="text-xs text-slate-400">{t("horizon.monitor")}</p>
          </div>
          <div
            className="bg-slate-900 rounded-xl border-2 border-slate-600 p-4 cursor-pointer hover:bg-slate-800 transition-colors"
            onClick={() => setActiveView("low_relevance")}
          >
            <p className="text-2xl font-bold text-slate-400">{scan.summary.low_relevance}</p>
            <p className="text-xs text-slate-400">{t("horizon.lowRelevance")}</p>
          </div>
          <div
            className="bg-slate-900 rounded-xl border border-slate-700 p-4 cursor-pointer hover:bg-slate-800 transition-colors"
            onClick={() => setActiveView("all")}
          >
            <p className="text-2xl font-bold text-white">{scan.summary.total_scanned}</p>
            <p className="text-xs text-slate-400">{t("horizon.totalScanned")}</p>
          </div>
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-2 mb-6">
        {(
          [
            { key: "all", labelKey: "horizon.allFilter" },
            { key: "directly_affects_you", labelKey: "horizon.criticalFilter" },
            { key: "monitor", labelKey: "horizon.monitorFilter" },
            { key: "low_relevance", labelKey: "horizon.lowFilter" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveView(tab.key)}
            className={clsx(
              "px-4 py-2 rounded-lg text-xs font-medium transition-colors",
              activeView === tab.key
                ? "bg-blue-600 text-white"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            )}
          >
            {t(tab.labelKey)}
          </button>
        ))}
      </div>

      {/* Items list */}
      {loading ? (
        <p className="text-slate-500 text-center py-20">{t("horizon.scanning")}</p>
      ) : filteredItems.length === 0 ? (
        <div className="text-center py-20 text-slate-500">
          <p className="text-lg mb-2">{t("horizon.noItems")}</p>
          <p className="text-sm">
            {scan && scan.summary.total_scanned === 0
              ? t("horizon.noItemsInDB")
              : t("horizon.noItemsFilter")}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredItems.map((item) => {
            const catConfig = CATEGORY_CONFIG[item.category];
            return (
              <div
                key={item.id}
                className={clsx(
                  "rounded-xl border-l-4 border border-slate-700 p-5 transition-all",
                  catConfig.border,
                  catConfig.bg
                )}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    {/* Header badges */}
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className={clsx("px-2 py-0.5 rounded-full text-[10px] font-bold", catConfig.badge)}>
                        {t(catConfig.labelKey).toUpperCase()}
                      </span>
                      {item.tags.map((tag) => (
                        <span
                          key={tag}
                          className={clsx(
                            "px-2 py-0.5 rounded-full text-[10px] font-bold",
                            tag === "enforcement" ? "bg-red-900/50 text-red-400" :
                            tag === "competition" ? "bg-purple-900/50 text-purple-400" :
                            tag === "deadline" ? "bg-amber-900/50 text-amber-400" :
                            "bg-slate-800 text-slate-400"
                          )}
                        >
                          {tag}
                        </span>
                      ))}
                      {item.urgency !== "normal" && (
                        <span
                          className={clsx(
                            "px-2 py-0.5 rounded-full text-[10px] font-bold",
                            item.urgency === "breaking" ? "bg-red-500 text-white" : "bg-amber-500 text-amber-950"
                          )}
                        >
                          {item.urgency.toUpperCase()}
                        </span>
                      )}
                      <span className="text-[10px] text-slate-500">{item.source}</span>
                      {item.date && (
                        <span className="text-[10px] text-slate-500">
                          {new Date(item.date).toLocaleDateString("de-DE")}
                        </span>
                      )}
                    </div>

                    {/* Title */}
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-semibold text-sm text-white hover:text-blue-400 transition-colors"
                    >
                      {item.title}
                    </a>

                    {/* Relevance reason */}
                    <p className="text-xs text-slate-400 mt-1">{item.relevance_reason}</p>

                    {/* Recommended action */}
                    <div className="mt-3 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg">
                      <p className="text-[10px] text-slate-500 uppercase mb-0.5">{t("horizon.recommendedAction")}</p>
                      <p className="text-xs text-slate-300">{item.recommended_action}</p>
                    </div>

                    {/* Deadline */}
                    {item.deadline && (
                      <div className="mt-2 px-3 py-2 bg-amber-950/20 border border-amber-800/30 rounded-lg">
                        <p className="text-xs text-amber-400">
                          <span className="font-bold">{t("horizon.deadlineDetected")}:</span> {item.deadline}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Relevance scores */}
                  <div className="flex flex-col items-center gap-2 flex-shrink-0">
                    <div className="text-center">
                      <p className="text-[10px] text-slate-500">{t("horizon.personalRelevance")}</p>
                      <div
                        className={clsx(
                          "w-12 h-12 rounded-lg flex items-center justify-center text-sm font-bold",
                          item.personal_relevance >= 8
                            ? "bg-red-950/50 text-red-400 border border-red-800"
                            : item.personal_relevance >= 5
                              ? "bg-amber-950/50 text-amber-400 border border-amber-800"
                              : "bg-slate-800 text-slate-500 border border-slate-700"
                        )}
                      >
                        {item.personal_relevance}
                      </div>
                    </div>
                    <div className="text-center">
                      <p className="text-[10px] text-slate-500">{t("horizon.originalRelevance")}</p>
                      <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400 border border-slate-700">
                        {item.original_relevance}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
