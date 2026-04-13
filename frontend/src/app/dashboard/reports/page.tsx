"use client";

import { useCallback, useState } from "react";
import { BACKEND_URL } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

// ---------------------------------------------------------------------------
// Download helper
// ---------------------------------------------------------------------------
async function downloadFile(url: string, filename: string) {
  const res = await fetch(`${BACKEND_URL}${url}`);
  if (!res.ok) throw new Error("Download failed");
  const blob = await res.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

// ---------------------------------------------------------------------------
// Spinner component
// ---------------------------------------------------------------------------
function Spinner() {
  return (
    <svg
      className="animate-spin h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Download icon
// ---------------------------------------------------------------------------
function DownloadIcon() {
  return (
    <svg
      className="w-4 h-4"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
function Toast({
  message,
  onClose,
}: {
  message: string;
  onClose: () => void;
}) {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 bg-green-600 text-white px-4 py-3 rounded-lg shadow-lg text-sm font-medium animate-fade-in">
      <svg
        className="w-5 h-5 flex-shrink-0"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      {message}
      <button
        onClick={onClose}
        className="ml-2 hover:text-green-200 transition-colors"
        aria-label="Dismiss notification"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Symbols for dropdowns
// ---------------------------------------------------------------------------
const SYMBOLS = [
  "BTC/USDT",
  "ETH/USDT",
  "SOL/USDT",
  "BNB/USDT",
  "XRP/USDT",
  "ADA/USDT",
  "DOT/USDT",
  "AVAX/USDT",
];

const SIGNAL_TYPES = ["composite", "technical", "sentiment", "on-chain"];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function ReportsPage() {
  const { t } = useTranslation();

  // Toast state
  const [toast, setToast] = useState<string | null>(null);
  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  }

  // PDF report state
  const [pdfPeriod, setPdfPeriod] = useState(
    () => new Date().toISOString().slice(0, 7) // "2026-04"
  );
  const [pdfLoading, setPdfLoading] = useState(false);

  // Excel price history state
  const [priceSymbol, setPriceSymbol] = useState("BTC/USDT");
  const [priceDays, setPriceDays] = useState(30);
  const [priceLoading, setPriceLoading] = useState(false);

  // Excel signal history state
  const [signalSymbol, setSignalSymbol] = useState("BTC/USDT");
  const [signalType, setSignalType] = useState("composite");
  const [signalDays, setSignalDays] = useState(30);
  const [signalLoading, setSignalLoading] = useState(false);

  // Excel trade history state
  const [tradeLoading, setTradeLoading] = useState(false);

  // Excel full report state
  const [fullLoading, setFullLoading] = useState(false);

  // Email digest state
  const [digestHtml, setDigestHtml] = useState<string | null>(null);
  const [digestLoading, setDigestLoading] = useState(false);
  const [sendLoading, setSendLoading] = useState(false);
  const [showSendConfirm, setShowSendConfirm] = useState(false);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handlePdfDownload = useCallback(async () => {
    setPdfLoading(true);
    try {
      await downloadFile(
        `/report/pdf?period=${pdfPeriod}`,
        `SignalDACH-Report-${pdfPeriod}.pdf`
      );
      showToast(t("reports.downloadComplete"));
    } catch {
      showToast(t("reports.downloadFailed"));
    } finally {
      setPdfLoading(false);
    }
  }, [pdfPeriod, t]);

  const handlePriceExport = useCallback(async () => {
    setPriceLoading(true);
    try {
      await downloadFile(
        `/report/excel/prices?symbol=${encodeURIComponent(priceSymbol)}&days=${priceDays}`,
        `PriceHistory-${priceSymbol.replace("/", "-")}-${priceDays}d.xlsx`
      );
      showToast(t("reports.downloadComplete"));
    } catch {
      showToast(t("reports.downloadFailed"));
    } finally {
      setPriceLoading(false);
    }
  }, [priceSymbol, priceDays, t]);

  const handleSignalExport = useCallback(async () => {
    setSignalLoading(true);
    try {
      await downloadFile(
        `/report/excel/signals?symbol=${encodeURIComponent(signalSymbol)}&signal_type=${signalType}&days=${signalDays}`,
        `SignalHistory-${signalSymbol.replace("/", "-")}-${signalType}-${signalDays}d.xlsx`
      );
      showToast(t("reports.downloadComplete"));
    } catch {
      showToast(t("reports.downloadFailed"));
    } finally {
      setSignalLoading(false);
    }
  }, [signalSymbol, signalType, signalDays, t]);

  const handleTradeExport = useCallback(async () => {
    setTradeLoading(true);
    try {
      await downloadFile(
        `/report/excel/trades`,
        `TradeHistory-${new Date().toISOString().slice(0, 10)}.xlsx`
      );
      showToast(t("reports.downloadComplete"));
    } catch {
      showToast(t("reports.downloadFailed"));
    } finally {
      setTradeLoading(false);
    }
  }, [t]);

  const handleFullExport = useCallback(async () => {
    setFullLoading(true);
    try {
      await downloadFile(
        `/report/excel/full`,
        `SignalDACH-FullReport-${new Date().toISOString().slice(0, 10)}.xlsx`
      );
      showToast(t("reports.downloadComplete"));
    } catch {
      showToast(t("reports.downloadFailed"));
    } finally {
      setFullLoading(false);
    }
  }, [t]);

  const handleDigestPreview = useCallback(async () => {
    setDigestLoading(true);
    try {
      const res = await fetch(
        `${BACKEND_URL}/report/digest/preview?email=user@example.com`
      );
      if (!res.ok) throw new Error("Preview failed");
      const html = await res.text();
      setDigestHtml(html);
    } catch {
      showToast(t("reports.previewFailed"));
    } finally {
      setDigestLoading(false);
    }
  }, [t]);

  const handleDigestSend = useCallback(async () => {
    setSendLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/report/digest/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) throw new Error("Send failed");
      showToast(t("reports.sendSuccess"));
    } catch {
      showToast(t("reports.sendFailed"));
    } finally {
      setSendLoading(false);
      setShowSendConfirm(false);
    }
  }, [t]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <>
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">{t("reports.title")}</h2>
        <p className="text-sm text-slate-400 mt-1">{t("reports.subtitle")}</p>
      </div>

      {/* PDF Report Card */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center">
            <svg
              className="w-5 h-5 text-red-400"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
              />
            </svg>
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">
              {t("reports.pdfReport")}
            </h3>
            <p className="text-xs text-slate-400">
              {t("reports.pdfDescription")}
            </p>
          </div>
        </div>
        <div className="flex items-end gap-4">
          <div>
            <label
              htmlFor="pdf-period"
              className="block text-xs text-slate-400 mb-1"
            >
              {t("reports.period")}
            </label>
            <input
              id="pdf-period"
              type="month"
              value={pdfPeriod}
              onChange={(e) => setPdfPeriod(e.target.value)}
              className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label={t("reports.period")}
            />
          </div>
          <button
            onClick={handlePdfDownload}
            disabled={pdfLoading}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
            aria-label={t("reports.generatePdf")}
          >
            {pdfLoading ? (
              <Spinner />
            ) : (
              <DownloadIcon />
            )}
            {pdfLoading ? t("reports.generating") : t("reports.generatePdf")}
          </button>
        </div>
      </div>

      {/* Excel Exports Section */}
      <h3 className="text-lg font-semibold text-white mb-4">
        {t("reports.excelExport")}
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        {/* Price History */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
          <h4 className="font-semibold text-sm text-white mb-3">
            {t("reports.priceHistory")}
          </h4>
          <div className="space-y-3">
            <div>
              <label
                htmlFor="price-symbol"
                className="block text-xs text-slate-400 mb-1"
              >
                {t("reports.symbol")}
              </label>
              <select
                id="price-symbol"
                value={priceSymbol}
                onChange={(e) => setPriceSymbol(e.target.value)}
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-label={t("reports.symbol")}
              >
                {SYMBOLS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                htmlFor="price-days"
                className="block text-xs text-slate-400 mb-1"
              >
                {t("reports.days")}
              </label>
              <input
                id="price-days"
                type="number"
                min={1}
                max={365}
                value={priceDays}
                onChange={(e) =>
                  setPriceDays(Math.max(1, parseInt(e.target.value) || 30))
                }
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-label={t("reports.days")}
              />
            </div>
            <button
              onClick={handlePriceExport}
              disabled={priceLoading}
              className="flex items-center gap-2 w-full justify-center px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
              aria-label={`${t("reports.download")} ${t("reports.priceHistory")}`}
            >
              {priceLoading ? <Spinner /> : <DownloadIcon />}
              {priceLoading ? t("reports.generating") : t("reports.download")}
            </button>
          </div>
        </div>

        {/* Signal History */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
          <h4 className="font-semibold text-sm text-white mb-3">
            {t("reports.signalHistory")}
          </h4>
          <div className="space-y-3">
            <div>
              <label
                htmlFor="signal-symbol"
                className="block text-xs text-slate-400 mb-1"
              >
                {t("reports.symbol")}
              </label>
              <select
                id="signal-symbol"
                value={signalSymbol}
                onChange={(e) => setSignalSymbol(e.target.value)}
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-label={t("reports.symbol")}
              >
                {SYMBOLS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                htmlFor="signal-type"
                className="block text-xs text-slate-400 mb-1"
              >
                {t("reports.signalType")}
              </label>
              <select
                id="signal-type"
                value={signalType}
                onChange={(e) => setSignalType(e.target.value)}
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-label={t("reports.signalType")}
              >
                {SIGNAL_TYPES.map((st) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                htmlFor="signal-days"
                className="block text-xs text-slate-400 mb-1"
              >
                {t("reports.days")}
              </label>
              <input
                id="signal-days"
                type="number"
                min={1}
                max={365}
                value={signalDays}
                onChange={(e) =>
                  setSignalDays(Math.max(1, parseInt(e.target.value) || 30))
                }
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-label={t("reports.days")}
              />
            </div>
            <button
              onClick={handleSignalExport}
              disabled={signalLoading}
              className="flex items-center gap-2 w-full justify-center px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
              aria-label={`${t("reports.download")} ${t("reports.signalHistory")}`}
            >
              {signalLoading ? <Spinner /> : <DownloadIcon />}
              {signalLoading ? t("reports.generating") : t("reports.download")}
            </button>
          </div>
        </div>

        {/* Trade History */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
          <h4 className="font-semibold text-sm text-white mb-3">
            {t("reports.tradeHistory")}
          </h4>
          <p className="text-xs text-slate-400 mb-4">
            {t("reports.tradeDescription")}
          </p>
          <button
            onClick={handleTradeExport}
            disabled={tradeLoading}
            className="flex items-center gap-2 w-full justify-center px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
            aria-label={`${t("reports.download")} ${t("reports.tradeHistory")}`}
          >
            {tradeLoading ? <Spinner /> : <DownloadIcon />}
            {tradeLoading ? t("reports.generating") : t("reports.download")}
          </button>
        </div>

        {/* Full Report */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
          <h4 className="font-semibold text-sm text-white mb-3">
            {t("reports.fullReport")}
          </h4>
          <p className="text-xs text-slate-400 mb-4">
            {t("reports.fullDescription")}
          </p>
          <button
            onClick={handleFullExport}
            disabled={fullLoading}
            className="flex items-center gap-2 w-full justify-center px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
            aria-label={`${t("reports.download")} ${t("reports.fullReport")}`}
          >
            {fullLoading ? <Spinner /> : <DownloadIcon />}
            {fullLoading ? t("reports.generating") : t("reports.download")}
          </button>
        </div>
      </div>

      {/* Email Digest Section */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <svg
              className="w-5 h-5 text-blue-400"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"
              />
            </svg>
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">
              {t("reports.emailDigest")}
            </h3>
            <p className="text-xs text-slate-400">
              {t("reports.emailDescription")}
            </p>
          </div>
        </div>

        <div className="flex gap-3 mb-4">
          <button
            onClick={handleDigestPreview}
            disabled={digestLoading}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
            aria-label={t("reports.preview")}
          >
            {digestLoading ? (
              <Spinner />
            ) : (
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
            )}
            {t("reports.preview")}
          </button>

          {!showSendConfirm ? (
            <button
              onClick={() => setShowSendConfirm(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
              aria-label={t("reports.sendNow")}
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
                />
              </svg>
              {t("reports.sendNow")}
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-sm text-amber-400">
                {t("reports.confirmSend")}
              </span>
              <button
                onClick={handleDigestSend}
                disabled={sendLoading}
                className="flex items-center gap-2 px-3 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                aria-label={t("reports.confirmYes")}
              >
                {sendLoading && <Spinner />}
                {t("reports.confirmYes")}
              </button>
              <button
                onClick={() => setShowSendConfirm(false)}
                className="px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm font-medium transition-colors"
                aria-label={t("reports.confirmNo")}
              >
                {t("reports.confirmNo")}
              </button>
            </div>
          )}
        </div>

        {digestHtml && (
          <div className="rounded-lg border border-slate-700 overflow-hidden">
            <iframe
              srcDoc={digestHtml}
              title="Email digest preview"
              className="w-full h-96 bg-white"
              sandbox="allow-same-origin"
            />
          </div>
        )}

        <p className="text-xs text-slate-500 mt-3">
          {t("reports.scheduleNote")}
        </p>
      </div>

      {/* Toast notification */}
      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </>
  );
}
