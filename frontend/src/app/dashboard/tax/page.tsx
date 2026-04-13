"use client";

import { useCallback, useEffect, useState } from "react";
import { clsx } from "clsx";
import { BACKEND_URL } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TaxRule {
  rule: string;
  tax_rate: string;
  exemption: string;
  note: string;
}

interface TaxCategory {
  name: string;
  rules: TaxRule[];
}

interface Deadline {
  date: string;
  description: string;
}

interface TaxRules {
  country: string;
  country_name: string;
  last_updated: string;
  summary: string;
  tax_categories: TaxCategory[];
  reporting_requirements: string[];
  deadlines: Deadline[];
  authorities: {
    name: string;
    reporting_to: string;
    guidance_url: string;
    key_legislation?: string[];
  };
  cantonal_notes?: Record<string, string>;
}

interface TaxEstimate {
  country: string;
  country_name: string;
  type: string;
  purchase_price: number;
  sale_price: number;
  gain: number;
  holding_days: number;
  holding_period_met: boolean;
  tax_rate_applied: number;
  estimated_tax: number;
  effective_rate: number;
  exemption_applied: string | null;
  notes: string[];
}

interface ComparisonRow {
  category: string;
  DE: Record<string, string> | string;
  CH: Record<string, string> | string;
  AT: Record<string, string> | string;
}

interface ComparisonData {
  comparison_date: string;
  countries: string[];
  comparison: ComparisonRow[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COUNTRIES = [
  { code: "DE", nameKey: "tax.germany", flag: "\uD83C\uDDE9\uD83C\uDDEA", accent: "border-yellow-500", bg: "bg-yellow-900/20", text: "text-yellow-400" },
  { code: "CH", nameKey: "tax.switzerland", flag: "\uD83C\uDDE8\uD83C\uDDED", accent: "border-red-500", bg: "bg-red-900/20", text: "text-red-400" },
  { code: "AT", nameKey: "tax.austria", flag: "\uD83C\uDDE6\uD83C\uDDF9", accent: "border-red-600", bg: "bg-red-900/20", text: "text-red-300" },
] as const;

const TRANSACTION_TYPES = [
  { value: "trading", labelKey: "tax.trading" },
  { value: "staking", labelKey: "tax.stakingLending" },
  { value: "mining", labelKey: "tax.mining" },
];

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function TaxPage() {
  const { t } = useTranslation();
  const [selectedCountry, setSelectedCountry] = useState("DE");
  const [activeTab, setActiveTab] = useState<"rules" | "calculator" | "compare">("rules");

  // Rules state
  const [rules, setRules] = useState<TaxRules | null>(null);
  const [rulesLoading, setRulesLoading] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  // Calculator state
  const [calcCountry, setCalcCountry] = useState("DE");
  const [purchasePrice, setPurchasePrice] = useState("");
  const [salePrice, setSalePrice] = useState("");
  const [holdingDays, setHoldingDays] = useState("");
  const [incomeTaxRate, setIncomeTaxRate] = useState("42");
  const [txType, setTxType] = useState("trading");
  const [estimate, setEstimate] = useState<TaxEstimate | null>(null);
  const [calcLoading, setCalcLoading] = useState(false);

  // Compare state
  const [comparison, setComparison] = useState<ComparisonData | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);

  // Load rules for selected country
  const loadRules = useCallback(async (country: string) => {
    setRulesLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/tax/rules?country=${country}`);
      const data = await res.json();
      setRules(data);
    } catch {
      setRules(null);
    } finally {
      setRulesLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRules(selectedCountry);
  }, [selectedCountry, loadRules]);

  // Load comparison
  const loadComparison = useCallback(async () => {
    setCompareLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/tax/compare`);
      const data = await res.json();
      setComparison(data);
    } catch {
      setComparison(null);
    } finally {
      setCompareLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "compare" && !comparison) {
      loadComparison();
    }
  }, [activeTab, comparison, loadComparison]);

  // Calculate tax
  async function handleCalculate(e: React.FormEvent) {
    e.preventDefault();
    if (!purchasePrice || !salePrice || !holdingDays) return;
    setCalcLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/tax/estimate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          country: calcCountry,
          purchase_price: parseFloat(purchasePrice),
          sale_price: parseFloat(salePrice),
          holding_days: parseInt(holdingDays),
          income_tax_rate: parseFloat(incomeTaxRate),
          type: txType,
        }),
      });
      const data = await res.json();
      setEstimate(data);
    } catch {
      setEstimate(null);
    } finally {
      setCalcLoading(false);
    }
  }

  function toggleCategory(name: string) {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  const countryConfig = COUNTRIES.find((c) => c.code === selectedCountry)!;

  return (
    <>
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">
          {t("tax.title")}
        </h2>
        <p className="text-sm text-slate-400 mt-1">
          {t("tax.subtitle")}
        </p>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-2 mb-6">
        {(
          [
            { key: "rules", label: t("tax.taxRules") },
            { key: "calculator", label: t("tax.taxCalculator") },
            { key: "compare", label: t("tax.countryComparison") },
          ] as const
        ).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={clsx(
              "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              activeTab === tab.key
                ? "bg-blue-600 text-white"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ================================================================ */}
      {/* TAX RULES TAB                                                    */}
      {/* ================================================================ */}
      {activeTab === "rules" && (
        <>
          {/* Country selector */}
          <div className="flex gap-3 mb-6">
            {COUNTRIES.map((c) => (
              <button
                key={c.code}
                onClick={() => setSelectedCountry(c.code)}
                className={clsx(
                  "flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold transition-all border-2",
                  selectedCountry === c.code
                    ? `${c.bg} ${c.text} ${c.accent}`
                    : "bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800"
                )}
              >
                <span className="text-lg">{c.flag}</span>
                {t(c.nameKey)}
              </button>
            ))}
          </div>

          {rulesLoading ? (
            <p className="text-slate-500 text-center py-20">{t("tax.loadingRules")}</p>
          ) : rules ? (
            <div className="space-y-6">
              {/* Summary */}
              <div className={clsx("bg-slate-900 rounded-xl border-2 p-6", countryConfig.accent)}>
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-2xl">{countryConfig.flag}</span>
                  <h3 className="text-lg font-bold text-white">{rules.country_name}</h3>
                  <span className="text-xs text-slate-500">{t("tax.updated")}: {rules.last_updated}</span>
                </div>
                <p className="text-sm text-slate-300 leading-relaxed">{rules.summary}</p>
              </div>

              {/* Tax categories (expandable) */}
              <div className="space-y-3">
                <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider">{t("tax.taxCategories")}</h3>
                {rules.tax_categories.map((cat) => {
                  const isExpanded = expandedCategories.has(cat.name);
                  return (
                    <div key={cat.name} className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
                      <button
                        onClick={() => toggleCategory(cat.name)}
                        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-slate-800/50 transition-colors"
                      >
                        <span className="font-semibold text-sm text-white">{cat.name}</span>
                        <svg
                          className={clsx("w-4 h-4 text-slate-400 transition-transform", isExpanded && "rotate-180")}
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={2}
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>
                      {isExpanded && (
                        <div className="px-5 pb-5 space-y-4">
                          {cat.rules.map((rule, idx) => (
                            <div key={idx} className="bg-slate-950 rounded-lg p-4 border border-slate-800">
                              <p className="text-sm text-white font-medium mb-2">{rule.rule}</p>
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-2">
                                <div>
                                  <span className="text-[10px] text-slate-500 uppercase tracking-wider">{t("tax.taxRate")}</span>
                                  <p className="text-xs text-slate-300">{rule.tax_rate}</p>
                                </div>
                                <div>
                                  <span className="text-[10px] text-slate-500 uppercase tracking-wider">{t("tax.exemption")}</span>
                                  <p className="text-xs text-slate-300">{rule.exemption}</p>
                                </div>
                              </div>
                              {rule.note && (
                                <div className="mt-2 px-3 py-2 bg-blue-950/30 border border-blue-900/50 rounded-lg">
                                  <p className="text-[11px] text-blue-300">
                                    <span className="font-bold">{t("tax.note")}:</span> {rule.note}
                                  </p>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Reporting requirements */}
              <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
                <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-3">{t("tax.reportingRequirements")}</h3>
                <ul className="space-y-2">
                  {rules.reporting_requirements.map((req, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-slate-400">
                      <span className="text-blue-400 mt-0.5 flex-shrink-0">&#x2022;</span>
                      {req}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Deadlines */}
              <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
                <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-3">{t("tax.importantDeadlines")}</h3>
                <div className="space-y-3">
                  {rules.deadlines.map((dl, idx) => {
                    const deadlineDate = new Date(dl.date);
                    const now = new Date();
                    const daysUntil = Math.ceil((deadlineDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
                    const isUrgent = daysUntil >= 0 && daysUntil <= 30;
                    const isPast = daysUntil < 0;

                    return (
                      <div
                        key={idx}
                        className={clsx(
                          "flex items-center justify-between px-4 py-3 rounded-lg border",
                          isPast
                            ? "bg-slate-950 border-slate-800 opacity-60"
                            : isUrgent
                              ? "bg-red-950/30 border-red-800/50"
                              : "bg-slate-950 border-slate-800"
                        )}
                      >
                        <div>
                          <p className="text-sm text-white font-medium">{dl.description}</p>
                          <p className="text-xs text-slate-500">{dl.date}</p>
                        </div>
                        <span
                          className={clsx(
                            "px-2 py-1 rounded-full text-[10px] font-bold",
                            isPast
                              ? "bg-slate-800 text-slate-500"
                              : isUrgent
                                ? "bg-red-900/50 text-red-400"
                                : "bg-slate-800 text-slate-400"
                          )}
                        >
                          {isPast ? t("tax.past") : `${daysUntil}${t("tax.daysLeft")}`}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Authorities */}
              <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
                <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-3">{t("tax.authoritiesLegislation")}</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase">{t("tax.authority")}</span>
                    <p className="text-sm text-white">{rules.authorities.name}</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase">{t("tax.reportsTo")}</span>
                    <p className="text-sm text-white">{rules.authorities.reporting_to}</p>
                  </div>
                </div>
                {rules.authorities.key_legislation && (
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase">{t("tax.keyLegislation")}</span>
                    <ul className="mt-1 space-y-1">
                      {rules.authorities.key_legislation.map((law, idx) => (
                        <li key={idx} className="text-xs text-slate-400">
                          <span className="text-blue-400">&#x00A7;</span> {law}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Cantonal notes (CH only) */}
              {rules.cantonal_notes && (
                <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
                  <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-3">{t("tax.cantonalNotes")}</h3>
                  <div className="space-y-2">
                    {Object.entries(rules.cantonal_notes).map(([canton, note]) => (
                      <div key={canton} className="flex items-start gap-3 px-4 py-3 bg-slate-950 rounded-lg">
                        <span className="text-xs font-bold text-red-400 uppercase min-w-[60px]">{canton}</span>
                        <p className="text-xs text-slate-400">{note}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-slate-500 text-center py-20">{t("tax.failedToLoadRules")}</p>
          )}
        </>
      )}

      {/* ================================================================ */}
      {/* TAX CALCULATOR TAB                                               */}
      {/* ================================================================ */}
      {activeTab === "calculator" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Calculator form */}
          <form onSubmit={handleCalculate} className="bg-slate-900 rounded-xl border border-slate-700 p-6 space-y-5">
            <h3 className="font-semibold text-white text-lg">{t("tax.taxEstimator")}</h3>
            <p className="text-xs text-slate-500">
              {t("tax.taxEstimatorDesc")}
            </p>

            {/* Country */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-2">{t("tax.country")}</label>
              <div className="flex gap-2">
                {COUNTRIES.map((c) => (
                  <button
                    key={c.code}
                    type="button"
                    onClick={() => setCalcCountry(c.code)}
                    className={clsx(
                      "flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold transition-colors border",
                      calcCountry === c.code
                        ? `${c.bg} ${c.text} ${c.accent}`
                        : "bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700"
                    )}
                  >
                    <span>{c.flag}</span> {c.code}
                  </button>
                ))}
              </div>
            </div>

            {/* Transaction type */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">{t("tax.transactionType")}</label>
              <select
                value={txType}
                onChange={(e) => setTxType(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-slate-800 text-sm text-white"
              >
                {TRANSACTION_TYPES.map((txn) => (
                  <option key={txn.value} value={txn.value}>{t(txn.labelKey)}</option>
                ))}
              </select>
            </div>

            {/* Purchase price */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">{t("tax.purchasePrice")}</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={purchasePrice}
                onChange={(e) => setPurchasePrice(e.target.value)}
                placeholder="10000"
                className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-slate-800 text-sm text-white placeholder:text-slate-500 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>

            {/* Sale price */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">{t("tax.salePrice")}</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={salePrice}
                onChange={(e) => setSalePrice(e.target.value)}
                placeholder="15000"
                className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-slate-800 text-sm text-white placeholder:text-slate-500 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>

            {/* Holding period */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">{t("tax.holdingPeriod")}</label>
              <input
                type="number"
                min="0"
                value={holdingDays}
                onChange={(e) => setHoldingDays(e.target.value)}
                placeholder="200"
                className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-slate-800 text-sm text-white placeholder:text-slate-500 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
              {holdingDays && parseInt(holdingDays) >= 365 && calcCountry === "DE" && (
                <p className="text-[10px] text-green-400 mt-1">
                  {t("tax.taxFreeDE")}
                </p>
              )}
            </div>

            {/* Income tax rate */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">
                {t("tax.incomeTaxRate")}{calcCountry === "AT" && txType === "trading" ? t("tax.kestNotUsed") : ""}
              </label>
              <input
                type="number"
                step="0.5"
                min="0"
                max="55"
                value={incomeTaxRate}
                onChange={(e) => setIncomeTaxRate(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-slate-800 text-sm text-white placeholder:text-slate-500 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={calcLoading || !purchasePrice || !salePrice || !holdingDays}
              className="w-full px-5 py-3 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {calcLoading ? t("tax.calculating") : t("tax.calculateEstimate")}
            </button>
          </form>

          {/* Results */}
          <div>
            {estimate ? (
              <div className="bg-slate-900 rounded-xl border border-slate-700 p-6 space-y-5">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-xl">{COUNTRIES.find((c) => c.code === estimate.country)?.flag}</span>
                  <h3 className="text-lg font-bold text-white">{estimate.country_name} — {t("tax.taxEstimate")}</h3>
                </div>

                {/* Key figures */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-950 rounded-lg p-4 border border-slate-800">
                    <p className="text-[10px] text-slate-500 uppercase">{t("tax.gainLoss")}</p>
                    <p className={clsx("text-2xl font-bold", estimate.gain >= 0 ? "text-green-400" : "text-red-400")}>
                      {estimate.gain >= 0 ? "+" : ""}{estimate.gain.toLocaleString("de-DE", { minimumFractionDigits: 2 })} EUR
                    </p>
                  </div>
                  <div className="bg-slate-950 rounded-lg p-4 border border-slate-800">
                    <p className="text-[10px] text-slate-500 uppercase">{t("tax.estimatedTax")}</p>
                    <p className={clsx("text-2xl font-bold", estimate.estimated_tax === 0 ? "text-green-400" : "text-amber-400")}>
                      {estimate.estimated_tax.toLocaleString("de-DE", { minimumFractionDigits: 2 })} EUR
                    </p>
                  </div>
                  <div className="bg-slate-950 rounded-lg p-4 border border-slate-800">
                    <p className="text-[10px] text-slate-500 uppercase">{t("tax.taxRateApplied")}</p>
                    <p className="text-xl font-bold text-white">{estimate.tax_rate_applied}%</p>
                  </div>
                  <div className="bg-slate-950 rounded-lg p-4 border border-slate-800">
                    <p className="text-[10px] text-slate-500 uppercase">{t("tax.effectiveRate")}</p>
                    <p className="text-xl font-bold text-white">{estimate.effective_rate}%</p>
                  </div>
                </div>

                {/* Holding period */}
                <div className={clsx(
                  "px-4 py-3 rounded-lg border",
                  estimate.holding_period_met
                    ? "bg-green-950/30 border-green-800/50"
                    : "bg-slate-950 border-slate-800"
                )}>
                  <p className="text-sm text-white">
                    {t("tax.holding")}: <span className="font-bold">{estimate.holding_days} {t("tax.daysLabel")}</span>
                    {estimate.holding_period_met && (
                      <span className="ml-2 text-green-400 font-bold">{t("tax.holdingPeriodMet")}</span>
                    )}
                  </p>
                </div>

                {/* Exemption */}
                {estimate.exemption_applied && (
                  <div className="px-4 py-3 bg-blue-950/30 border border-blue-800/50 rounded-lg">
                    <p className="text-xs text-blue-300">
                      <span className="font-bold">{t("tax.exemption")}:</span> {estimate.exemption_applied}
                    </p>
                  </div>
                )}

                {/* Notes */}
                {estimate.notes.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold text-slate-400 uppercase">{t("tax.notes")}</h4>
                    {estimate.notes.map((note, idx) => (
                      <div key={idx} className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg">
                        <p className="text-xs text-slate-300">{note}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Disclaimer */}
                <div className="px-4 py-3 bg-amber-950/20 border border-amber-800/30 rounded-lg">
                  <p className="text-[10px] text-amber-400">
                    {t("tax.disclaimer")}
                  </p>
                </div>
              </div>
            ) : (
              <div className="bg-slate-900 rounded-xl border border-slate-700 p-12 text-center">
                <svg className="w-12 h-12 mx-auto text-slate-600 mb-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 15.75V18m-7.5-6.75h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25V13.5zm0 2.25h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25V18zm2.498-6.75h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007V13.5zm0 2.25h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007V18zm2.504-6.75h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V13.5zm0 2.25h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V18zm2.498-6.75h.008v.008H15.75v-.008zm0 2.25h.008v.008H15.75V13.5zM8.25 6h7.5v2.25h-7.5V6zM12 2.25c-1.892 0-3.758.11-5.593.322C5.307 2.7 4.5 3.65 4.5 4.757V19.5a2.25 2.25 0 002.25 2.25h10.5a2.25 2.25 0 002.25-2.25V4.757c0-1.108-.806-2.057-1.907-2.185A48.507 48.507 0 0012 2.25z" />
                </svg>
                <p className="text-slate-400 text-sm mb-1">{t("tax.enterDetails")}</p>
                <p className="text-slate-500 text-xs">{t("tax.fillInForm")}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ================================================================ */}
      {/* COMPARISON TAB                                                   */}
      {/* ================================================================ */}
      {activeTab === "compare" && (
        <>
          {compareLoading ? (
            <p className="text-slate-500 text-center py-20">{t("tax.loadingComparison")}</p>
          ) : comparison ? (
            <div className="space-y-4">
              <p className="text-xs text-slate-500 mb-4">
                {t("tax.comparisonDesc")}
              </p>

              {comparison.comparison.map((row, idx) => (
                <div key={idx} className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
                  <div className="px-5 py-3 bg-slate-800/50 border-b border-slate-700">
                    <h3 className="text-sm font-bold text-white">{row.category}</h3>
                  </div>
                  <div className="grid grid-cols-3 divide-x divide-slate-700">
                    {(["DE", "CH", "AT"] as const).map((code) => {
                      const countryInfo = COUNTRIES.find((c) => c.code === code)!;
                      const data = row[code];
                      return (
                        <div key={code} className="p-4">
                          <div className="flex items-center gap-1.5 mb-2">
                            <span className="text-sm">{countryInfo.flag}</span>
                            <span className="text-xs font-bold text-slate-300">{code}</span>
                          </div>
                          {typeof data === "string" ? (
                            <p className="text-xs text-slate-400">{data}</p>
                          ) : (
                            <div className="space-y-1.5">
                              {Object.entries(data).map(([key, value]) => (
                                <div key={key}>
                                  <span className="text-[10px] text-slate-500 uppercase">{key.replace(/_/g, " ")}</span>
                                  <p className="text-xs text-slate-300">{value}</p>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-center py-20">{t("tax.failedComparison")}</p>
          )}
        </>
      )}
    </>
  );
}
