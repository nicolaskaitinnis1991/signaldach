"use client";

import { useState } from "react";
import { clsx } from "clsx";
import {
  BACKEND_URL,
  triggerScrape,
  testWebhook,
  useMonitoringHealth,
  useKillSwitchStatus,
  useFeatureFlags,
  useHealthReady,
  useHealthEnv,
  useHealthStartup,
  useSystemStatus,
  useRiskLimits,
  activateKillSwitch,
  deactivateKillSwitch,
  type FeatureFlag,
} from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { ConfirmDialog } from "@/components/ConfirmDialog";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function StatusDot({ status }: { status: "healthy" | "unhealthy" | "unknown" }) {
  return (
    <div
      className={clsx(
        "w-2.5 h-2.5 rounded-full flex-shrink-0",
        status === "healthy" && "bg-green-400",
        status === "unhealthy" && "bg-red-400",
        status === "unknown" && "bg-slate-500"
      )}
      role="status"
      aria-label={status}
    />
  );
}

function SectionCard({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "bg-slate-900 rounded-xl border border-slate-700 p-6",
        className
      )}
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function SettingsPage() {
  const { t } = useTranslation();

  // Existing hooks
  const {
    data: health,
    error: healthError,
    isLoading: loadingStatus,
    mutate: refreshHealth,
  } = useMonitoringHealth();

  // New hooks
  const { data: killSwitch, mutate: mutateKillSwitch } = useKillSwitchStatus();
  const { data: flagsData } = useFeatureFlags();
  const { data: healthReady } = useHealthReady();
  const { data: healthEnv } = useHealthEnv();
  const { data: healthStartup } = useHealthStartup();
  const { data: systemStatus } = useSystemStatus();
  const { data: riskLimits } = useRiskLimits();

  // Kill switch state
  const [killReason, setKillReason] = useState("");
  const [killLoading, setKillLoading] = useState(false);
  const [killError, setKillError] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<"activate" | "deactivate" | null>(null);

  // Scrape state (preserved from original)
  const [scraping, setScraping] = useState(false);
  const [scrapeResult, setScrapeResult] = useState<string | null>(null);

  // Webhook state (preserved from original)
  const [webhookUrl, setWebhookUrl] = useState("");
  const [testingWebhook, setTestingWebhook] = useState(false);
  const [webhookResult, setWebhookResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  // Normalize flags data (API may return {flags:[...]} or [...])
  const flags: FeatureFlag[] = Array.isArray(flagsData)
    ? flagsData
    : (flagsData as { flags?: FeatureFlag[] })?.flags ?? [];

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------
  async function handleKillSwitchActivate() {
    setKillLoading(true);
    setKillError(null);
    try {
      await activateKillSwitch(killReason || "Manual activation");
      await mutateKillSwitch();
      setKillReason("");
    } catch (err) {
      setKillError(err instanceof Error ? err.message : "Activation failed");
    } finally {
      setKillLoading(false);
      setConfirmAction(null);
    }
  }

  async function handleKillSwitchDeactivate() {
    setKillLoading(true);
    setKillError(null);
    try {
      await deactivateKillSwitch();
      await mutateKillSwitch();
    } catch (err) {
      setKillError(err instanceof Error ? err.message : "Deactivation failed");
    } finally {
      setKillLoading(false);
      setConfirmAction(null);
    }
  }

  async function handleScrape() {
    setScraping(true);
    setScrapeResult(null);
    try {
      await triggerScrape();
      setScrapeResult("Scrape triggered successfully. Items will appear shortly.");
      setTimeout(() => refreshHealth(), 5000);
    } catch (err) {
      setScrapeResult(
        `Error: ${err instanceof Error ? err.message : "Failed to trigger scrape"}`
      );
    } finally {
      setScraping(false);
    }
  }

  async function handleTestWebhook() {
    if (!webhookUrl.trim()) return;
    setTestingWebhook(true);
    setWebhookResult(null);
    try {
      const result = await testWebhook(webhookUrl.trim());
      setWebhookResult({
        ok: result.ok,
        message: result.ok
          ? "Webhook test successful! Check the endpoint for the test payload."
          : "Webhook test failed. Check the URL and try again.",
      });
    } catch (err) {
      setWebhookResult({
        ok: false,
        message: `Error: ${err instanceof Error ? err.message : "Test failed"}`,
      });
    } finally {
      setTestingWebhook(false);
    }
  }

  function healthStatus(val: string | undefined): "healthy" | "unhealthy" | "unknown" {
    if (!val) return "unknown";
    if (val === "ok" || val === "healthy" || val === "connected") return "healthy";
    if (val === "error" || val === "unhealthy" || val === "disconnected") return "unhealthy";
    return "unknown";
  }

  const isKillActive = killSwitch?.active === true;

  return (
    <>
      {/* Confirmation dialog */}
      <ConfirmDialog
        open={confirmAction !== null}
        title={
          confirmAction === "activate"
            ? t("settings.activate")
            : t("settings.deactivate")
        }
        message={
          confirmAction === "activate"
            ? t("settings.confirmActivate")
            : t("settings.confirmDeactivate")
        }
        confirmLabel={
          confirmAction === "activate"
            ? t("settings.activate")
            : t("settings.deactivate")
        }
        confirmVariant={confirmAction === "activate" ? "danger" : "primary"}
        onConfirm={
          confirmAction === "activate"
            ? handleKillSwitchActivate
            : handleKillSwitchDeactivate
        }
        onCancel={() => setConfirmAction(null)}
      />

      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">{t("settings.title")}</h2>
        <p className="text-sm text-slate-400 mt-1">{t("settings.subtitle")}</p>
      </div>

      <div className="space-y-6">
        {/* ================================================================
            Section 1: Kill Switch
            ================================================================ */}
        <div
          className={clsx(
            "rounded-xl border-2 p-6",
            isKillActive
              ? "bg-red-950/40 border-red-600"
              : "bg-slate-900 border-slate-700"
          )}
          role="region"
          aria-label={t("settings.killSwitch")}
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                {/* Warning icon */}
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
                    d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                  />
                </svg>
                {t("settings.killSwitch")}
              </h3>
              <p className="text-sm text-slate-400 mt-0.5">
                {t("settings.killSwitchDesc")}
              </p>
            </div>

            {/* Status badge */}
            <div
              className={clsx(
                "px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider",
                isKillActive
                  ? "bg-red-600/30 text-red-300 border border-red-500 animate-pulse"
                  : "bg-green-600/20 text-green-400 border border-green-600"
              )}
              role="status"
              aria-label={isKillActive ? t("settings.active") : t("settings.inactive")}
            >
              {isKillActive ? t("settings.active") : t("settings.inactive")}
            </div>
          </div>

          {/* Last activation info */}
          {killSwitch?.activated_at && (
            <div className="mb-4 p-3 bg-slate-800/50 rounded-lg text-sm">
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-slate-400">
                <span>
                  <span className="font-medium text-slate-300">
                    {t("settings.activatedBy")}:
                  </span>{" "}
                  {killSwitch.activated_by ?? "---"}
                </span>
                <span>
                  <span className="font-medium text-slate-300">
                    {t("settings.activatedAt")}:
                  </span>{" "}
                  {new Date(killSwitch.activated_at).toLocaleString()}
                </span>
                {killSwitch.reason && (
                  <span>
                    <span className="font-medium text-slate-300">
                      {t("settings.reason")}:
                    </span>{" "}
                    {killSwitch.reason}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Reason input + action buttons */}
          <div className="flex flex-col sm:flex-row gap-3">
            {!isKillActive && (
              <input
                type="text"
                value={killReason}
                onChange={(e) => setKillReason(e.target.value)}
                placeholder={t("settings.reasonPlaceholder")}
                aria-label={t("settings.reason")}
                className="flex-1 px-3 py-2 rounded-lg border border-slate-700 bg-slate-800 text-sm text-white placeholder:text-slate-500 focus:ring-2 focus:ring-red-500 focus:outline-none"
              />
            )}
            {isKillActive ? (
              <button
                onClick={() => setConfirmAction("deactivate")}
                disabled={killLoading}
                className="px-5 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-green-500"
                aria-label={t("settings.deactivate")}
              >
                {killLoading ? "..." : t("settings.deactivate")}
              </button>
            ) : (
              <button
                onClick={() => setConfirmAction("activate")}
                disabled={killLoading}
                className="px-5 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-red-500"
                aria-label={t("settings.activate")}
              >
                {killLoading ? "..." : t("settings.activate")}
              </button>
            )}
          </div>

          {killError && (
            <div className="mt-3 p-3 bg-red-950/50 border border-red-800 rounded-lg">
              <p className="text-sm text-red-400">{killError}</p>
            </div>
          )}
        </div>

        {/* ================================================================
            Section 2: Feature Flags
            ================================================================ */}
        <SectionCard>
          <h3 className="font-semibold text-white mb-1">
            {t("settings.featureFlags")}
          </h3>
          <p className="text-sm text-slate-400 mb-4">
            {t("settings.featureFlagsDesc")}
          </p>

          {flags.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" role="table">
                <thead>
                  <tr className="text-left text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800">
                    <th className="pb-2 pr-4">{t("settings.flagName")}</th>
                    <th className="pb-2 pr-4">{t("settings.flagValue")}</th>
                    <th className="pb-2 pr-4">{t("settings.flagDefault")}</th>
                    <th className="pb-2">{t("settings.flagEnvKey")}</th>
                  </tr>
                </thead>
                <tbody>
                  {flags.map((flag) => (
                    <tr
                      key={flag.name}
                      className="border-b border-slate-800/50 last:border-0"
                    >
                      <td className="py-2.5 pr-4 text-slate-300 font-medium">
                        {flag.name}
                      </td>
                      <td className="py-2.5 pr-4">
                        <span
                          className={clsx(
                            "px-2 py-0.5 rounded text-xs font-bold",
                            flag.value
                              ? "bg-green-600/20 text-green-400"
                              : "bg-slate-700 text-slate-400"
                          )}
                        >
                          {flag.value ? t("settings.on") : t("settings.off")}
                        </span>
                      </td>
                      <td className="py-2.5 pr-4 text-slate-500 text-xs">
                        {flag.default ? t("settings.on") : t("settings.off")}
                      </td>
                      <td className="py-2.5">
                        <code className="text-xs bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">
                          {flag.env_key}
                        </code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-slate-500">{t("settings.noFlags")}</p>
          )}
        </SectionCard>

        {/* ================================================================
            Section 3: System Health
            ================================================================ */}
        <SectionCard>
          <h3 className="font-semibold text-white mb-4">
            {t("settings.systemHealth")}
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            {/* Database */}
            <div className="bg-slate-800/50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-1">
                <StatusDot status={healthStatus(healthReady?.database)} />
                <span className="text-sm font-medium text-slate-300">
                  {t("settings.database")}
                </span>
              </div>
              <p className="text-xs text-slate-500">
                {healthReady?.database ?? t("settings.unknown")}
              </p>
            </div>

            {/* Redis */}
            <div className="bg-slate-800/50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-1">
                <StatusDot status={healthStatus(healthReady?.redis)} />
                <span className="text-sm font-medium text-slate-300">
                  {t("settings.redis")}
                </span>
              </div>
              <p className="text-xs text-slate-500">
                {healthReady?.redis ?? t("settings.unknown")}
              </p>
            </div>

            {/* Scheduler */}
            <div className="bg-slate-800/50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-1">
                <StatusDot status={healthStatus(healthReady?.scheduler)} />
                <span className="text-sm font-medium text-slate-300">
                  {t("settings.scheduler")}
                </span>
              </div>
              <p className="text-xs text-slate-500">
                {healthReady?.scheduler ?? t("settings.unknown")}
              </p>
            </div>

            {/* Uptime */}
            <div className="bg-slate-800/50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-1">
                <StatusDot status="healthy" />
                <span className="text-sm font-medium text-slate-300">
                  {t("settings.uptime")}
                </span>
              </div>
              <p className="text-xs text-slate-500">
                {healthReady?.uptime_seconds
                  ? `${Math.round(healthReady.uptime_seconds / 3600)}h ${Math.round((healthReady.uptime_seconds % 3600) / 60)}m`
                  : "---"}
              </p>
            </div>
          </div>

          {/* Env validation warnings */}
          {healthEnv && (
            <div className="mt-2">
              <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                {t("settings.envValidation")}
              </h4>
              {(healthEnv.warnings?.length ?? 0) > 0 || (healthEnv.missing?.length ?? 0) > 0 ? (
                <div className="space-y-1">
                  {healthEnv.warnings?.map((w, i) => (
                    <div
                      key={`warn-${i}`}
                      className="bg-amber-950/50 border border-amber-800 rounded-lg px-3 py-2"
                    >
                      <p className="text-xs text-amber-400">{w}</p>
                    </div>
                  ))}
                  {healthEnv.missing?.map((m, i) => (
                    <div
                      key={`miss-${i}`}
                      className="bg-red-950/50 border border-red-800 rounded-lg px-3 py-2"
                    >
                      <p className="text-xs text-red-400">Missing: {m}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-green-400">{t("settings.noWarnings")}</p>
              )}
            </div>
          )}
        </SectionCard>

        {/* ================================================================
            Section 4: Fund Configuration
            ================================================================ */}
        <SectionCard>
          <h3 className="font-semibold text-white mb-1">
            {t("settings.fundConfig")}
          </h3>
          <p className="text-sm text-slate-400 mb-4">
            {t("settings.fundConfigDesc")}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Risk Limits */}
            <div>
              <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-3">
                {t("settings.riskLimits")}
              </h4>
              {riskLimits ? (
                <div className="bg-slate-800/50 rounded-lg divide-y divide-slate-700">
                  {Object.entries(riskLimits).map(([key, value]) => (
                    <div key={key} className="flex justify-between px-3 py-2">
                      <span className="text-xs text-slate-400">
                        {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                      </span>
                      <span className="text-xs font-medium text-slate-300">
                        {typeof value === "number"
                          ? key.includes("pct")
                            ? `${value}%`
                            : value.toLocaleString()
                          : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500">---</p>
              )}
            </div>

            {/* Fee Structure & MiCA */}
            <div className="space-y-4">
              <div>
                <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-3">
                  {t("settings.feeStructure")}
                </h4>
                <div className="bg-slate-800/50 rounded-lg divide-y divide-slate-700">
                  <div className="flex justify-between px-3 py-2">
                    <span className="text-xs text-slate-400">
                      {t("settings.managementFee")}
                    </span>
                    <span className="text-xs font-medium text-slate-300">2%</span>
                  </div>
                  <div className="flex justify-between px-3 py-2">
                    <span className="text-xs text-slate-400">
                      {t("settings.performanceFee")}
                    </span>
                    <span className="text-xs font-medium text-slate-300">20%</span>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-3">
                  {t("settings.micaCompliance")}
                </h4>
                <div className="bg-slate-800/50 rounded-lg px-3 py-2 flex items-center gap-2">
                  <StatusDot status="healthy" />
                  <span className="text-xs font-medium text-green-400">
                    {t("settings.compliant")}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </SectionCard>

        {/* ================================================================
            Section 5: System Info
            ================================================================ */}
        <SectionCard>
          <h3 className="font-semibold text-white mb-4">
            {t("settings.systemInfo")}
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="bg-slate-800/50 rounded-lg p-3">
              <p className="text-xs text-slate-400 mb-1">
                {t("settings.backendUrl")}
              </p>
              <code className="text-xs text-slate-300">{BACKEND_URL}</code>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3">
              <p className="text-xs text-slate-400 mb-1">
                {t("settings.status")}
              </p>
              <span
                className={clsx(
                  "text-xs font-medium",
                  health ? "text-green-400" : "text-red-400"
                )}
              >
                {health ? t("settings.connected") : t("common.disconnected")}
              </span>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3">
              <p className="text-xs text-slate-400 mb-1">
                {t("settings.databaseType")}
              </p>
              <span className="text-xs text-slate-300">
                {systemStatus?.db_type ?? systemStatus?.database ??
                  (systemStatus?.db_size?.includes("PostgreSQL") ? "PostgreSQL" : "SQLite")}
              </span>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3">
              <p className="text-xs text-slate-400 mb-1">
                {t("settings.sourcesCount")}
              </p>
              <p className="text-lg font-bold text-white">
                {systemStatus?.active_sources ?? "---"}
              </p>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3">
              <p className="text-xs text-slate-400 mb-1">
                {t("settings.itemsCount")}
              </p>
              <p className="text-lg font-bold text-white">
                {systemStatus?.total_items?.toLocaleString() ?? "---"}
              </p>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3">
              <p className="text-xs text-slate-400 mb-1">
                {t("settings.authStatus")}
              </p>
              <span className="text-xs text-green-400 font-medium">
                {health ? t("settings.connected") : t("common.disconnected")}
              </span>
            </div>
          </div>
        </SectionCard>

        {/* ================================================================
            Original sections: System Status, Scrape, Webhook
            ================================================================ */}

        {/* System Status (from monitoring/health) */}
        <SectionCard>
          <h3 className="font-semibold text-white mb-4">
            {t("settings.systemStatus")}
          </h3>
          {loadingStatus ? (
            <p className="text-sm text-slate-500">{t("settings.loadingStatus")}</p>
          ) : health ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-3">
                <div
                  className={clsx(
                    "w-3 h-3 rounded-full",
                    health.status === "healthy"
                      ? "bg-green-400"
                      : "bg-amber-400"
                  )}
                />
                <span className="text-sm font-medium text-slate-300">
                  {health.status === "healthy"
                    ? t("settings.allHealthy")
                    : t("settings.degraded")}
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <p className="text-lg font-bold text-white">
                    {(health.checks.database.items ?? 0).toLocaleString()}
                  </p>
                  <p className="text-xs text-slate-400">{t("common.totalItems")}</p>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <p className="text-lg font-bold text-white">
                    {health.checks.database.sources ?? 0}
                  </p>
                  <p className="text-xs text-slate-400">{t("sidebar.sources")}</p>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <p className="text-lg font-bold text-white">
                    {health.checks.scrapers.total_scrapes}
                  </p>
                  <p className="text-xs text-slate-400">{t("settings.totalScrapes")}</p>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <p className="text-sm font-medium text-white">
                    {Math.round(health.checks.uptime.uptime_seconds / 3600)}h
                  </p>
                  <p className="text-xs text-slate-400">{t("settings.uptime")}</p>
                </div>
              </div>
              {health.checks.scrapers.total_errors > 0 && (
                <div className="bg-amber-950/50 border border-amber-800 rounded-lg p-3">
                  <p className="text-sm text-amber-400">
                    {health.checks.scrapers.total_errors}{" "}
                    {t("settings.scrapeErrors")}
                  </p>
                </div>
              )}
            </div>
          ) : healthError ? (
            <div className="bg-red-950/50 border border-red-800 rounded-lg p-3">
              <p className="text-sm text-red-400">
                {t("settings.unableToConnect")} {BACKEND_URL}
              </p>
            </div>
          ) : null}
        </SectionCard>

        {/* Scrape Control */}
        <SectionCard>
          <h3 className="font-semibold text-white mb-2">
            {t("settings.manualScrape")}
          </h3>
          <p className="text-sm text-slate-400 mb-4">
            {t("settings.scrapeDesc")}
          </p>
          <div className="flex items-center gap-3">
            <button
              onClick={handleScrape}
              disabled={scraping}
              className="px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
              aria-label={t("settings.scrapeNow")}
            >
              {scraping ? t("settings.scraping") : t("settings.scrapeNow")}
            </button>
            {scrapeResult && (
              <span
                className={clsx(
                  "text-sm",
                  scrapeResult.startsWith("Error")
                    ? "text-red-400"
                    : "text-green-400"
                )}
              >
                {scrapeResult}
              </span>
            )}
          </div>
        </SectionCard>

        {/* Webhook Test */}
        <SectionCard>
          <h3 className="font-semibold text-white mb-2">
            {t("settings.webhookTest")}
          </h3>
          <p className="text-sm text-slate-400 mb-4">
            {t("settings.testDesc")}
          </p>
          <div className="flex gap-3">
            <input
              type="url"
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              placeholder="https://hooks.slack.com/services/..."
              className="flex-1 px-3 py-2 rounded-lg border border-slate-700 bg-slate-800 text-sm text-white placeholder:text-slate-500 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              aria-label={t("settings.webhookTest")}
            />
            <button
              onClick={handleTestWebhook}
              disabled={testingWebhook || !webhookUrl.trim()}
              className="px-5 py-2 bg-slate-700 text-white text-sm font-medium rounded-lg hover:bg-slate-600 transition-colors disabled:opacity-50"
              aria-label={t("settings.test")}
            >
              {testingWebhook ? t("settings.testing") : t("settings.test")}
            </button>
          </div>
          {webhookResult && (
            <div
              className={clsx(
                "mt-3 p-3 rounded-lg text-sm",
                webhookResult.ok
                  ? "bg-green-950/50 text-green-400 border border-green-800"
                  : "bg-red-950/50 text-red-400 border border-red-800"
              )}
            >
              {webhookResult.message}
            </div>
          )}
        </SectionCard>
      </div>
    </>
  );
}
