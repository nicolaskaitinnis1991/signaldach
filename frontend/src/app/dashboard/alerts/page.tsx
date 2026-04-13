"use client";

import { useEffect, useState } from "react";
import { clsx } from "clsx";
import {
  BACKEND_URL,
  createAlert,
  deleteAlert,
  toggleAlert,
  type Alert,
} from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

const ALL_CATEGORIES = ["regulation", "market", "competition", "sentiment"];
const URGENCY_OPTIONS = ["normal", "high", "breaking"] as const;

function NewAlertForm({
  onCreated,
  onCancel,
}: {
  onCreated: () => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [minUrgency, setMinUrgency] = useState<"normal" | "high" | "breaking">("normal");
  const [minRelevance, setMinRelevance] = useState(5);
  const [keywords, setKeywords] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [email, setEmail] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function toggleCategory(cat: string) {
    setCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError(t("alerts.nameRequired"));
      return;
    }
    setSaving(true);
    setError("");
    try {
      await createAlert({
        name: name.trim(),
        enabled,
        conditions: {
          categories: categories.length > 0 ? categories : ALL_CATEGORIES,
          min_urgency: minUrgency,
          min_relevance: minRelevance,
          keywords: keywords
            .split(",")
            .map((k) => k.trim())
            .filter(Boolean),
        },
        channels: {
          webhook_url: webhookUrl.trim() || undefined,
          email: email.trim() || undefined,
        },
      });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("alerts.failedCreate"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-slate-900 rounded-xl border border-slate-700 p-6 space-y-5"
    >
      <h3 className="font-semibold text-white text-lg">{t("alerts.newAlert")}</h3>

      {error && (
        <div className="p-3 bg-red-950/50 border border-red-800 rounded-lg text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Name */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">
          {t("alerts.name")}
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. BaFin Breaking Alerts"
          className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-slate-800 text-sm text-white placeholder:text-slate-500 focus:ring-2 focus:ring-blue-500 focus:outline-none"
        />
      </div>

      {/* Categories */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-2">
          {t("alerts.categories")}
        </label>
        <div className="flex gap-2 flex-wrap">
          {ALL_CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => toggleCategory(cat)}
              className={clsx(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                categories.includes(cat)
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              )}
            >
              {t(`feed.${cat}`)}
            </button>
          ))}
        </div>
        <p className="text-[10px] text-slate-500 mt-1">
          {t("alerts.leaveEmptyForAll")}
        </p>
      </div>

      {/* Min Urgency */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">
          {t("alerts.minUrgency")}
        </label>
        <select
          value={minUrgency}
          onChange={(e) =>
            setMinUrgency(e.target.value as "normal" | "high" | "breaking")
          }
          className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-slate-800 text-sm text-white"
        >
          {URGENCY_OPTIONS.map((u) => (
            <option key={u} value={u}>
              {u === "breaking" ? t("common.breaking") : u === "high" ? t("feed.high") : t("feed.normal")}
            </option>
          ))}
        </select>
      </div>

      {/* Min Relevance */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">
          {t("alerts.minRelevance")}: {minRelevance}
        </label>
        <input
          type="range"
          min={1}
          max={10}
          value={minRelevance}
          onChange={(e) => setMinRelevance(Number(e.target.value))}
          className="w-full"
        />
        <div className="flex justify-between text-[10px] text-slate-500">
          <span>1 ({t("alerts.lowLabel")})</span>
          <span>10 ({t("alerts.criticalLabel")})</span>
        </div>
      </div>

      {/* Keywords */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">
          {t("alerts.keywords")}
        </label>
        <input
          type="text"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          placeholder="MiCA, BaFin, crypto license"
          className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-slate-800 text-sm text-white placeholder:text-slate-500 focus:ring-2 focus:ring-blue-500 focus:outline-none"
        />
      </div>

      {/* Webhook URL */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">
          {t("alerts.webhookUrl")}
        </label>
        <input
          type="url"
          value={webhookUrl}
          onChange={(e) => setWebhookUrl(e.target.value)}
          placeholder="https://hooks.slack.com/services/..."
          className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-slate-800 text-sm text-white placeholder:text-slate-500 focus:ring-2 focus:ring-blue-500 focus:outline-none"
        />
      </div>

      {/* Email */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">
          {t("alerts.email")}
        </label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="alerts@example.com"
          className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-slate-800 text-sm text-white placeholder:text-slate-500 focus:ring-2 focus:ring-blue-500 focus:outline-none"
        />
      </div>

      {/* Enable toggle */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setEnabled(!enabled)}
          className={clsx(
            "relative w-11 h-6 rounded-full transition-colors",
            enabled ? "bg-blue-600" : "bg-slate-600"
          )}
        >
          <div
            className={clsx(
              "absolute top-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow",
              enabled ? "translate-x-5.5 left-0.5" : "left-0.5"
            )}
            style={{ transform: enabled ? "translateX(22px)" : "translateX(2px)" }}
          />
        </button>
        <span className="text-sm text-slate-300">
          {enabled ? t("common.enabled") : t("common.disabled")}
        </span>
      </div>

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={saving}
          className="px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {saving ? t("alerts.creating") : t("alerts.createAlert")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-5 py-2 bg-slate-800 text-slate-300 text-sm font-medium rounded-lg hover:bg-slate-700 transition-colors"
        >
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

const CATEGORY_COLORS: Record<string, string> = {
  regulation: "bg-purple-900/50 text-purple-300",
  competition: "bg-orange-900/50 text-orange-300",
  market: "bg-blue-900/50 text-blue-300",
  sentiment: "bg-green-900/50 text-green-300",
};

export default function AlertsPage() {
  const { t } = useTranslation();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  async function loadAlerts() {
    try {
      const res = await fetch(`${BACKEND_URL}/alerts`);
      const data = await res.json();
      setAlerts(data.alerts || []);
    } catch {
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAlerts();
  }, []);

  async function handleDelete(id: string) {
    try {
      await deleteAlert(id);
      await loadAlerts();
    } catch {
      // ignore
    }
  }

  async function handleToggle(id: string, enabled: boolean) {
    try {
      await toggleAlert(id, !enabled);
      await loadAlerts();
    } catch {
      // ignore
    }
  }

  return (
    <>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">{t("alerts.title")}</h2>
          <p className="text-sm text-slate-400 mt-1">
            {t("alerts.subtitle")}
          </p>
        </div>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            {t("alerts.newAlert")}
          </button>
        )}
      </div>

      {showForm && (
        <div className="mb-6">
          <NewAlertForm
            onCreated={() => {
              setShowForm(false);
              loadAlerts();
            }}
            onCancel={() => setShowForm(false)}
          />
        </div>
      )}

      {loading ? (
        <p className="text-slate-500 text-center py-10">{t("alerts.loadingAlerts")}</p>
      ) : alerts.length === 0 && !showForm ? (
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-8 text-center">
          <p className="text-slate-400 mb-2">{t("alerts.noAlerts")}</p>
          <p className="text-xs text-slate-500">
            {t("alerts.noAlertsDesc")}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={clsx(
                "bg-slate-900 rounded-xl border border-slate-700 p-5",
                !alert.enabled && "opacity-60"
              )}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-semibold text-sm text-white">
                      {alert.name}
                    </h3>
                    <span
                      className={clsx(
                        "px-2 py-0.5 rounded-full text-[10px] font-bold",
                        alert.enabled
                          ? "bg-green-900/50 text-green-400"
                          : "bg-slate-800 text-slate-500"
                      )}
                    >
                      {alert.enabled ? "ACTIVE" : "PAUSED"}
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-1 mb-2">
                    {(alert.conditions?.categories || []).map((cat) => (
                      <span
                        key={cat}
                        className={clsx(
                          "px-2 py-0.5 rounded-full text-[10px] font-semibold",
                          CATEGORY_COLORS[cat] || "bg-slate-800 text-slate-400"
                        )}
                      >
                        {cat}
                      </span>
                    ))}
                  </div>

                  <div className="flex flex-wrap gap-3 text-xs text-slate-400">
                    {alert.conditions?.min_urgency && (
                      <span>
                        {t("alerts.minUrgency")}: {"\u2265"} {alert.conditions.min_urgency}
                      </span>
                    )}
                    {alert.conditions?.min_relevance != null && (
                      <span>
                        {t("alerts.minRelevance")}: {"\u2265"} {alert.conditions.min_relevance}
                      </span>
                    )}
                    {(alert.conditions?.keywords?.length ?? 0) > 0 && (
                      <span>{t("alerts.keywords")}: {alert.conditions!.keywords!.join(", ")}</span>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-3 mt-2 text-xs text-slate-500">
                    {alert.channels?.webhook_url && (
                      <span>{t("alerts.webhookUrl")}: {alert.channels.webhook_url.slice(0, 40)}...</span>
                    )}
                    {alert.channels?.email && <span>{t("alerts.email")}: {alert.channels.email}</span>}
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => handleToggle(alert.id, alert.enabled)}
                    className={clsx(
                      "relative w-11 h-6 rounded-full transition-colors",
                      alert.enabled ? "bg-blue-600" : "bg-slate-600"
                    )}
                  >
                    <div
                      className="absolute top-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow"
                      style={{
                        transform: alert.enabled
                          ? "translateX(22px)"
                          : "translateX(2px)",
                      }}
                    />
                  </button>
                  <button
                    onClick={() => handleDelete(alert.id)}
                    className="p-1.5 text-slate-500 hover:text-red-400 transition-colors"
                    title={t("alerts.deleteAlert")}
                  >
                    {"\u2715"}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
