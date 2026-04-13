"use client";

import { clsx } from "clsx";
import type { FeedItem } from "@/lib/api";
import { stripHtml, timeAgo } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

const CATEGORY_COLORS: Record<string, string> = {
  regulation: "bg-purple-900/50 text-purple-300",
  competition: "bg-orange-900/50 text-orange-300",
  market: "bg-blue-900/50 text-blue-300",
  sentiment: "bg-green-900/50 text-green-300",
};

const URGENCY_STYLES: Record<string, string> = {
  normal: "",
  high: "border-l-4 border-l-amber-500",
  breaking: "border-l-4 border-l-red-500 bg-red-950/30",
};

export function FeedCard({
  item,
  showSource = false,
}: {
  item: FeedItem;
  showSource?: boolean;
}) {
  const { t } = useTranslation();
  const cleanSummary = item.summary ? stripHtml(item.summary) : "";

  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className={clsx(
        "block bg-slate-900 rounded-xl border border-slate-700 p-5 hover:border-slate-600 transition-all duration-200",
        URGENCY_STYLES[item.urgency]
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span
              className={clsx(
                "inline-block px-2 py-0.5 rounded-full text-xs font-semibold",
                CATEGORY_COLORS[item.category] || "bg-slate-800 text-slate-400"
              )}
            >
              {item.category}
            </span>
            {item.urgency !== "normal" && (
              <span
                className={clsx(
                  "inline-block px-2 py-0.5 rounded-full text-xs font-bold",
                  item.urgency === "breaking"
                    ? "bg-red-500 text-white"
                    : "bg-amber-500 text-amber-950"
                )}
              >
                {item.urgency.toUpperCase()}
              </span>
            )}
            {showSource && item.source_name && (
              <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-400">
                {item.source_name}
              </span>
            )}
            <span className="text-xs text-slate-500">
              {timeAgo(item.published_at)}
            </span>
          </div>

          <h3 className="font-semibold text-white text-sm leading-snug mb-1">
            {item.title}
          </h3>

          {cleanSummary && (
            <p className="text-xs text-slate-400 line-clamp-2">{cleanSummary}</p>
          )}
        </div>

        <div className="flex flex-col items-center gap-1 flex-shrink-0">
          <div
            className={clsx(
              "w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold",
              item.relevance_score >= 8
                ? "bg-red-950/50 text-red-400"
                : item.relevance_score >= 5
                  ? "bg-amber-950/50 text-amber-400"
                  : "bg-slate-800 text-slate-500"
            )}
          >
            {item.relevance_score}
          </div>
          <span className="text-[10px] text-slate-500">{t("common.relevance")}</span>
        </div>
      </div>

      {item.sentiment !== null && item.sentiment !== undefined && (
        <div className="mt-3 flex items-center gap-2">
          <div className="h-1.5 flex-1 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={clsx(
                "h-full rounded-full",
                item.sentiment > 0.2
                  ? "bg-green-500"
                  : item.sentiment < -0.2
                    ? "bg-red-500"
                    : "bg-slate-500"
              )}
              style={{ width: `${Math.abs(item.sentiment) * 100}%` }}
            />
          </div>
          <span className="text-[10px] text-slate-500 w-8 text-right">
            {item.sentiment > 0 ? "+" : ""}
            {item.sentiment.toFixed(1)}
          </span>
        </div>
      )}

      {item.author && (
        <p className="mt-2 text-[10px] text-slate-500">by {item.author}</p>
      )}
    </a>
  );
}
