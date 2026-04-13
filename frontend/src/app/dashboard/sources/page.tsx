"use client";

import { useEffect, useState } from "react";
import { clsx } from "clsx";
import { BACKEND_URL, type Source } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

export default function SourcesPage() {
  const { t } = useTranslation();
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  useEffect(() => {
    loadSources();
  }, []);

  async function loadSources() {
    try {
      const res = await fetch(`${BACKEND_URL}/sources`);
      const data = await res.json();
      setSources(data.sources || []);
    } catch {
      setSources([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleSeed() {
    setSeeding(true);
    try {
      await fetch(`${BACKEND_URL}/sources/seed-defaults`, { method: "POST" });
      await loadSources();
    } finally {
      setSeeding(false);
    }
  }

  const CATEGORY_COLORS: Record<string, string> = {
    regulation: "bg-purple-900/50 text-purple-300",
    competition: "bg-orange-900/50 text-orange-300",
    market: "bg-blue-900/50 text-blue-300",
    sentiment: "bg-green-900/50 text-green-300",
  };

  return (
    <>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">{t("sources.title")}</h2>
          <p className="text-sm text-slate-400 mt-1">
            {t("sources.subtitle")}
          </p>
        </div>
        <button
          onClick={handleSeed}
          disabled={seeding}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {seeding ? t("sources.seeding") : t("sources.seedDefaults")}
        </button>
      </div>

      {loading ? (
        <p className="text-slate-500 text-center py-10">{t("sources.loadingSources")}</p>
      ) : sources.length === 0 ? (
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-8 text-center">
          <p className="text-slate-400 mb-2">{t("sources.noSources")}</p>
          <p className="text-xs text-slate-500">
            {t("sources.noSourcesDesc")}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {sources.map((source) => (
            <div
              key={source.id}
              className="bg-slate-900 rounded-xl border border-slate-700 p-4 flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <div
                  className={clsx(
                    "w-2 h-2 rounded-full",
                    source.enabled ? "bg-green-400" : "bg-slate-600"
                  )}
                />
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-sm text-white">{source.name}</p>
                    <span
                      className={clsx(
                        "px-1.5 py-0.5 rounded text-[10px] font-semibold",
                        source.enabled
                          ? "bg-green-900/50 text-green-400"
                          : "bg-slate-800 text-slate-500"
                      )}
                    >
                      {source.enabled ? t("sources.enabled") : t("sources.disabled")}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500">
                    {source.type} &middot; every {source.scrape_frequency_minutes}min
                    {source.last_scraped_at &&
                      ` \u00B7 last scraped: ${new Date(source.last_scraped_at).toLocaleString()}`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={clsx(
                    "px-2 py-0.5 rounded-full text-xs font-semibold",
                    CATEGORY_COLORS[source.category] || "bg-slate-800 text-slate-400"
                  )}
                >
                  {source.category}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
