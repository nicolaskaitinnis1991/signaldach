"use client";

import { useState, useCallback } from "react";
import { clsx } from "clsx";
import {
  BACKEND_URL,
  usePaperPortfolio,
  usePaperOrders,
  usePaperPerformance,
} from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Position {
  symbol: string;
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  pnl_pct: number;
}

interface Portfolio {
  total_value: number;
  cash: number;
  unrealized_pnl?: number;
  total_trades?: number;
  position_count?: number;
  positions: Position[];
}

interface Order {
  id: string;
  created_at: string;
  symbol: string;
  side: "BUY" | "SELL";
  order_type: "MARKET" | "LIMIT";
  quantity: number;
  fill_price: number | null;
  status: "FILLED" | "CANCELLED" | "REJECTED" | "PENDING";
  reason: string | null;
}

interface Performance {
  total_return_pct: number;
  win_rate: number;
  sharpe_ratio: number;
  max_drawdown: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const SYMBOLS = [
  "BTC/USDT",
  "ETH/USDT",
  "SOL/USDT",
  "XRP/USDT",
  "ADA/USDT",
  "DOT/USDT",
  "AVAX/USDT",
  "MATIC/USDT",
  "LINK/USDT",
  "DOGE/USDT",
];

const ORDER_TYPES = ["MARKET", "LIMIT"] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatUsd(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPct(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function pnlColor(value: number): string {
  if (value > 0) return "text-green-400";
  if (value < 0) return "text-red-400";
  return "text-slate-400";
}

function statusBadge(status: Order["status"]): { bg: string; text: string } {
  switch (status) {
    case "FILLED":
      return { bg: "bg-green-500/20 border-green-500/30", text: "text-green-300" };
    case "CANCELLED":
      return { bg: "bg-slate-500/20 border-slate-500/30", text: "text-slate-300" };
    case "REJECTED":
      return { bg: "bg-red-500/20 border-red-500/30", text: "text-red-300" };
    case "PENDING":
      return { bg: "bg-yellow-500/20 border-yellow-500/30", text: "text-yellow-300" };
    default:
      return { bg: "bg-slate-500/20 border-slate-500/30", text: "text-slate-300" };
  }
}

function timeStr(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function PaperTradingPage() {
  const { t } = useTranslation();
  const { data: portfolio, mutate: mutatePortfolio } = usePaperPortfolio();
  const { data: orders, mutate: mutateOrders } = usePaperOrders(50);
  const { data: performance } = usePaperPerformance();

  // Order form state
  const [symbol, setSymbol] = useState(SYMBOLS[0]);
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [orderType, setOrderType] = useState<"MARKET" | "LIMIT">("MARKET");
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");

  const p = (portfolio as Portfolio | undefined) ?? null;
  const orderList = ((orders as { orders?: Order[] } | undefined)?.orders ?? []) as Order[];
  const perf = (performance as Performance | undefined) ?? null;

  // Submit order
  const submitOrder = useCallback(async () => {
    setFormError("");
    setFormSuccess("");
    const quantity = parseFloat(qty);
    if (!quantity || quantity <= 0) {
      setFormError("Quantity must be greater than 0");
      return;
    }
    if (orderType === "LIMIT" && (!price || parseFloat(price) <= 0)) {
      setFormError("Limit price must be greater than 0");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/paper/order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          side,
          order_type: orderType,
          quantity,
          price: price ? parseFloat(price) : undefined,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.message || `Order failed: ${res.status}`);
      }
      setFormSuccess("Order submitted successfully");
      setQty("");
      setPrice("");
      mutatePortfolio();
      mutateOrders();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Order submission failed");
    } finally {
      setSubmitting(false);
    }
  }, [symbol, side, orderType, qty, price, mutatePortfolio, mutateOrders]);

  // Close position
  const closePosition = useCallback(
    async (posSymbol: string, posQty: number) => {
      try {
        await fetch(`${BACKEND_URL}/api/paper/order`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            symbol: posSymbol,
            side: "SELL",
            order_type: "MARKET",
            quantity: posQty,
          }),
        });
        mutatePortfolio();
        mutateOrders();
      } catch {
        // silently fail, user will see no change
      }
    },
    [mutatePortfolio, mutateOrders]
  );

  return (
    <div className="space-y-6">
      {/* ---- Header ---- */}
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white">
            {t("paperTrading.title")}
          </h1>
          <span className="px-2 py-0.5 text-xs font-bold rounded bg-orange-500/20 border border-orange-500/30 text-orange-300 uppercase tracking-wider">
            {t("paperTrading.simulation")}
          </span>
        </div>
        <p className="text-sm text-slate-400 mt-1">
          {t("paperTrading.subtitle")}
        </p>
      </div>

      {/* ---- Portfolio Summary ---- */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard
          label={t("paperTrading.totalValue")}
          value={p ? formatUsd(p.total_value) : "--"}
        />
        <SummaryCard
          label={t("paperTrading.cashAvailable")}
          value={p ? formatUsd(p.cash) : "--"}
        />
        <SummaryCard
          label={t("paperTrading.unrealizedPnl")}
          value={p ? formatUsd(p.unrealized_pnl ?? 0) : "--"}
          valueClass={p ? pnlColor(p.unrealized_pnl ?? 0) : undefined}
        />
        <SummaryCard
          label={t("paperTrading.totalTrades")}
          value={p ? String(p.total_trades ?? p.position_count ?? 0) : "--"}
        />
      </div>

      {/* ---- Order Form ---- */}
      <section
        className="bg-slate-900 rounded-xl border border-slate-700 p-6"
        aria-label="New order form"
      >
        <h2 className="text-lg font-semibold text-white mb-4">
          {t("paperTrading.newOrder")}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4 items-end">
          {/* Symbol */}
          <div>
            <label
              htmlFor="pt-symbol"
              className="block text-xs text-slate-400 mb-1"
            >
              {t("paperTrading.symbol")}
            </label>
            <select
              id="pt-symbol"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label="Select trading pair"
            >
              {SYMBOLS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          {/* Side toggle */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">
              {t("paperTrading.side")}
            </label>
            <div className="flex rounded-lg overflow-hidden border border-slate-600">
              <button
                type="button"
                onClick={() => setSide("BUY")}
                className={clsx(
                  "flex-1 px-4 py-2 text-sm font-medium transition-colors",
                  side === "BUY"
                    ? "bg-green-600 text-white"
                    : "bg-slate-800 text-slate-400 hover:text-white"
                )}
                aria-pressed={side === "BUY"}
                aria-label="Buy side"
              >
                BUY
              </button>
              <button
                type="button"
                onClick={() => setSide("SELL")}
                className={clsx(
                  "flex-1 px-4 py-2 text-sm font-medium transition-colors",
                  side === "SELL"
                    ? "bg-red-600 text-white"
                    : "bg-slate-800 text-slate-400 hover:text-white"
                )}
                aria-pressed={side === "SELL"}
                aria-label="Sell side"
              >
                SELL
              </button>
            </div>
          </div>

          {/* Order Type */}
          <div>
            <label
              htmlFor="pt-order-type"
              className="block text-xs text-slate-400 mb-1"
            >
              {t("paperTrading.orderType")}
            </label>
            <select
              id="pt-order-type"
              value={orderType}
              onChange={(e) =>
                setOrderType(e.target.value as "MARKET" | "LIMIT")
              }
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label="Select order type"
            >
              {ORDER_TYPES.map((ot) => (
                <option key={ot} value={ot}>
                  {ot}
                </option>
              ))}
            </select>
          </div>

          {/* Quantity */}
          <div>
            <label
              htmlFor="pt-qty"
              className="block text-xs text-slate-400 mb-1"
            >
              {t("paperTrading.quantity")}
            </label>
            <input
              id="pt-qty"
              type="number"
              step="any"
              min="0"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              placeholder="0.00"
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label="Order quantity"
            />
          </div>

          {/* Price (limit only) */}
          <div>
            <label
              htmlFor="pt-price"
              className="block text-xs text-slate-400 mb-1"
            >
              {t("paperTrading.price")}
            </label>
            <input
              id="pt-price"
              type="number"
              step="any"
              min="0"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder={orderType === "LIMIT" ? "0.00" : "Market"}
              disabled={orderType === "MARKET"}
              className={clsx(
                "w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500",
                orderType === "MARKET" && "opacity-50 cursor-not-allowed"
              )}
              aria-label="Limit price"
            />
          </div>

          {/* Submit */}
          <div>
            <button
              type="button"
              onClick={submitOrder}
              disabled={submitting || !qty}
              className={clsx(
                "w-full px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                submitting || !qty
                  ? "bg-slate-700 text-slate-500 cursor-not-allowed"
                  : "bg-blue-600 hover:bg-blue-500 text-white"
              )}
              aria-label="Submit order"
            >
              {submitting
                ? t("paperTrading.submitting")
                : t("paperTrading.submitOrder")}
            </button>
          </div>
        </div>

        {/* Form messages */}
        {formError && (
          <p className="mt-3 text-sm text-red-400" role="alert">
            {formError}
          </p>
        )}
        {formSuccess && (
          <p className="mt-3 text-sm text-green-400" role="status">
            {formSuccess}
          </p>
        )}
      </section>

      {/* ---- Open Positions ---- */}
      <section
        className="bg-slate-900 rounded-xl border border-slate-700 p-6"
        aria-label="Open positions"
      >
        <h2 className="text-lg font-semibold text-white mb-4">
          {t("paperTrading.openPositions")}
        </h2>
        {!p || p.positions.length === 0 ? (
          <p className="text-sm text-slate-500">
            {t("paperTrading.noPositions")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" role="table">
              <thead>
                <tr className="text-left text-xs text-slate-400 border-b border-slate-700">
                  <th className="pb-3 pr-4">{t("paperTrading.symbol")}</th>
                  <th className="pb-3 pr-4">{t("paperTrading.quantity")}</th>
                  <th className="pb-3 pr-4">{t("paperTrading.avgEntry")}</th>
                  <th className="pb-3 pr-4">{t("paperTrading.currentPrice")}</th>
                  <th className="pb-3 pr-4">{t("paperTrading.unrealizedPnl")}</th>
                  <th className="pb-3 pr-4">{t("paperTrading.pnlPct")}</th>
                  <th className="pb-3">{t("paperTrading.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {p.positions.map((pos) => (
                  <tr
                    key={pos.symbol}
                    className="border-b border-slate-800 last:border-0"
                  >
                    <td className="py-3 pr-4 font-medium text-white">
                      {pos.symbol}
                    </td>
                    <td className="py-3 pr-4 text-slate-300">
                      {pos.quantity.toFixed(6)}
                    </td>
                    <td className="py-3 pr-4 text-slate-300">
                      {formatUsd(pos.avg_entry_price)}
                    </td>
                    <td className="py-3 pr-4 text-slate-300">
                      {formatUsd(pos.current_price)}
                    </td>
                    <td
                      className={clsx("py-3 pr-4 font-medium", pnlColor(pos.unrealized_pnl))}
                    >
                      {formatUsd(pos.unrealized_pnl)}
                    </td>
                    <td
                      className={clsx("py-3 pr-4 font-medium", pnlColor(pos.pnl_pct))}
                    >
                      {formatPct(pos.pnl_pct)}
                    </td>
                    <td className="py-3">
                      <button
                        type="button"
                        onClick={() => closePosition(pos.symbol, pos.quantity)}
                        className="px-3 py-1 text-xs font-medium rounded bg-red-500/20 border border-red-500/30 text-red-300 hover:bg-red-500/30 transition-colors"
                        aria-label={`Close ${pos.symbol} position`}
                      >
                        {t("paperTrading.close")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ---- Order History ---- */}
      <section
        className="bg-slate-900 rounded-xl border border-slate-700 p-6"
        aria-label="Order history"
      >
        <h2 className="text-lg font-semibold text-white mb-4">
          {t("paperTrading.orderHistory")}
        </h2>
        {orderList.length === 0 ? (
          <p className="text-sm text-slate-500">
            {t("paperTrading.noOrders")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" role="table">
              <thead>
                <tr className="text-left text-xs text-slate-400 border-b border-slate-700">
                  <th className="pb-3 pr-4">{t("paperTrading.time")}</th>
                  <th className="pb-3 pr-4">{t("paperTrading.symbol")}</th>
                  <th className="pb-3 pr-4">{t("paperTrading.side")}</th>
                  <th className="pb-3 pr-4">{t("paperTrading.type")}</th>
                  <th className="pb-3 pr-4">{t("paperTrading.quantity")}</th>
                  <th className="pb-3 pr-4">{t("paperTrading.fillPrice")}</th>
                  <th className="pb-3 pr-4">{t("paperTrading.status")}</th>
                  <th className="pb-3">{t("paperTrading.reason")}</th>
                </tr>
              </thead>
              <tbody>
                {orderList.map((order) => {
                  const badge = statusBadge(order.status);
                  return (
                    <tr
                      key={order.id}
                      className="border-b border-slate-800 last:border-0"
                    >
                      <td className="py-3 pr-4 text-slate-400 whitespace-nowrap">
                        {timeStr(order.created_at)}
                      </td>
                      <td className="py-3 pr-4 font-medium text-white">
                        {order.symbol}
                      </td>
                      <td
                        className={clsx(
                          "py-3 pr-4 font-medium",
                          order.side === "BUY" ? "text-green-400" : "text-red-400"
                        )}
                      >
                        {order.side}
                      </td>
                      <td className="py-3 pr-4 text-slate-300">
                        {order.order_type}
                      </td>
                      <td className="py-3 pr-4 text-slate-300">
                        {order.quantity.toFixed(6)}
                      </td>
                      <td className="py-3 pr-4 text-slate-300">
                        {order.fill_price ? formatUsd(order.fill_price) : "--"}
                      </td>
                      <td className="py-3 pr-4">
                        <span
                          className={clsx(
                            "px-2 py-0.5 text-xs font-medium rounded border",
                            badge.bg,
                            badge.text
                          )}
                        >
                          {order.status}
                        </span>
                      </td>
                      <td className="py-3 text-slate-500 text-xs max-w-[200px] truncate">
                        {order.reason ?? "--"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ---- Performance Metrics ---- */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard
          label={t("paperTrading.totalReturn")}
          value={perf ? formatPct(perf.total_return_pct) : "--"}
          valueClass={perf ? pnlColor(perf.total_return_pct) : undefined}
        />
        <SummaryCard
          label={t("paperTrading.winRate")}
          value={perf ? `${perf.win_rate.toFixed(1)}%` : "--"}
        />
        <SummaryCard
          label={t("paperTrading.sharpeRatio")}
          value={perf ? perf.sharpe_ratio.toFixed(2) : "--"}
        />
        <SummaryCard
          label={t("paperTrading.maxDrawdown")}
          value={perf ? formatPct(perf.max_drawdown) : "--"}
          valueClass={perf ? "text-red-400" : undefined}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Summary Card
// ---------------------------------------------------------------------------
function SummaryCard({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
      <p className="text-xs text-slate-400 uppercase tracking-wider">{label}</p>
      <p className={clsx("text-2xl font-bold mt-1", valueClass ?? "text-white")}>
        {value}
      </p>
    </div>
  );
}
