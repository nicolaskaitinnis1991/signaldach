import useSWR, { type SWRConfiguration } from "swr";

// ---------------------------------------------------------------------------
// Backend URL
// ---------------------------------------------------------------------------
export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface FeedItem {
  id: string;
  title: string;
  summary: string;
  content: string;
  url: string;
  author: string;
  published_at: string | null;
  category: "regulation" | "competition" | "market" | "sentiment";
  relevance_score: number;
  urgency: "normal" | "high" | "breaking";
  sentiment: number | null;
  source_id: string;
  source_name?: string;
  ai_metadata: Record<string, unknown>;
  created_at: string;
}

export interface Source {
  id: string;
  name: string;
  type: string;
  category: string;
  url: string;
  enabled: boolean;
  last_scraped_at: string | null;
  scrape_frequency_minutes: number;
}

export interface Alert {
  id: string;
  name: string;
  enabled: boolean;
  conditions: {
    categories?: string[];
    min_urgency?: "normal" | "high" | "breaking";
    min_relevance?: number;
    keywords?: string[];
  };
  channels: {
    webhook_url?: string;
    email?: string;
  };
  tenant_id?: string;
  user_id?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface Analytics {
  period_days: number;
  summary: {
    total_items: number;
    breaking_count: number;
    high_count: number;
    avg_relevance: number;
    avg_sentiment: number | null;
  };
  by_category: Array<{ category: string; count: number }>;
  by_urgency: Array<{ urgency: string; count: number }>;
  daily: Array<{ day: string; category: string; count: number }>;
  sentiment_trend: Array<{ day: string; avg_sentiment: number; count: number }>;
  top_keywords: Array<{ keyword: string; count: number }>;
  source_breakdown?: Array<{
    source_name: string;
    source_category: string;
    item_count: number;
    avg_relevance: number;
  }>;
  hourly_heatmap?: Array<{
    day_of_week: number;
    hour: number;
    count: number;
  }>;
}

export interface MonitoringHealth {
  status: "healthy" | "degraded";
  checks: {
    database: { status: string; sources?: number; items?: number; error?: string };
    uptime: { started_at: string; uptime_seconds: number };
    memory: { rss_mb?: number; status?: string };
    scrapers: {
      total_scrapes: number;
      total_errors: number;
      total_items_ingested: number;
    };
  };
}

export interface Report {
  [key: string]: unknown;
}

export interface SystemStatus {
  db_size: string;
  db_type?: string;
  database?: string;
  database_status?: string;
  total_items: number;
  active_sources: number;
  sources_count?: number;
  items_count?: number;
  last_scrape: string | null;
  [key: string]: unknown;
}

export interface ItemsResponse {
  items: FeedItem[];
  count: number;
  total?: number;
}

export interface SourcesResponse {
  sources: Source[];
}

export interface AlertsResponse {
  alerts: Alert[];
}

// ---------------------------------------------------------------------------
// API Error with structured code
// ---------------------------------------------------------------------------
export class ApiError extends Error {
  status: number;
  code: string;
  retryable: boolean;

  constructor(status: number, code: string, message: string, retryable: boolean) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.retryable = retryable;
  }
}

// ---------------------------------------------------------------------------
// Fetcher with structured error parsing
// ---------------------------------------------------------------------------
async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    let code = "UNKNOWN_ERROR";
    let message = `${res.status} ${res.statusText}`;
    let retryable = res.status >= 500 || res.status === 429;
    try {
      const body = await res.json();
      if (body.error_code) code = body.error_code;
      if (body.message) message = body.message;
      if (typeof body.retryable === "boolean") retryable = body.retryable;
    } catch {
      // body wasn't JSON
    }
    throw new ApiError(res.status, code, message, retryable);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// SWR retry config with exponential backoff
// ---------------------------------------------------------------------------
const DEFAULT_SWR_CONFIG: SWRConfiguration = {
  onErrorRetry: (error, _key, _config, revalidate, { retryCount }) => {
    // Don't retry on 4xx (except 429 rate limit)
    if (error instanceof ApiError && !error.retryable) return;
    if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 429) return;
    // Max 3 retries
    if (retryCount >= 3) return;
    // Exponential backoff: 1s, 2s, 4s
    const delay = Math.min(1000 * Math.pow(2, retryCount), 8000);
    setTimeout(() => revalidate({ retryCount }), delay);
  },
};

// ---------------------------------------------------------------------------
// SWR Hooks
// ---------------------------------------------------------------------------
export function useItems(
  params?: {
    category?: string;
    urgency?: string;
    q?: string;
    limit?: number;
    offset?: number;
    sort?: string;
  },
  config?: SWRConfiguration
) {
  const searchParams = new URLSearchParams();
  if (params?.category) searchParams.set("category", params.category);
  if (params?.urgency) searchParams.set("urgency", params.urgency);
  if (params?.q) searchParams.set("q", params.q);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  if (params?.sort) searchParams.set("sort", params.sort);

  return useSWR<ItemsResponse>(
    `${BACKEND_URL}/items?${searchParams}`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 30000, ...config }
  );
}

export function useSources(config?: SWRConfiguration) {
  return useSWR<SourcesResponse>(
    `${BACKEND_URL}/sources`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 60000, ...config }
  );
}

export function useAnalytics(days: number = 7, config?: SWRConfiguration) {
  return useSWR<Analytics>(
    `${BACKEND_URL}/analytics?days=${days}`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 60000, ...config }
  );
}

export function useAlerts(config?: SWRConfiguration) {
  return useSWR<AlertsResponse>(
    `${BACKEND_URL}/alerts`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 30000, ...config }
  );
}

export function useSystemStatus(config?: SWRConfiguration) {
  return useSWR<SystemStatus>(
    `${BACKEND_URL}/status`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 30000, ...config }
  );
}

export function useReport(hours: number = 24, config?: SWRConfiguration) {
  return useSWR<Report>(
    `${BACKEND_URL}/report?hours=${hours}`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 300000, ...config }
  );
}

export function useMonitoringHealth(config?: SWRConfiguration) {
  return useSWR<MonitoringHealth>(
    `${BACKEND_URL}/monitoring/health`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 30000, ...config }
  );
}

// ---------------------------------------------------------------------------
// Market Data Hooks
// ---------------------------------------------------------------------------
export interface PriceTick {
  symbol: string;
  price: number;
  change_pct_24h: number | null;
  volume_24h: number | null;
  exchange: string;
  ts: string;
}

export interface MarketSummary {
  btc: PriceTick | null;
  eth: PriceTick | null;
  fear_greed: { value: number; classification: string; ts: string } | null;
  global: { total_market_cap: number | null; btc_dominance: number | null };
  data_freshness: Record<string, string>;
}

export interface SignalResult {
  symbol: string;
  overall_signal: string;
  overall_score: number;
  confidence: number;
  reasoning: string;
  risk_factors: string[];
  key_drivers: string[];
  agents: Array<{
    agent: string;
    signal: string;
    score: number;
    confidence: number;
    reasoning: string;
  }>;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  data?: Record<string, unknown>;
  sources?: string[];
  suggested_actions?: string[];
}

export function useMarketSummary(config?: SWRConfiguration) {
  return useSWR<MarketSummary>(
    `${BACKEND_URL}/api/market/summary`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 30000, ...config }
  );
}

export function useMarketPrices(config?: SWRConfiguration) {
  return useSWR<{ prices: PriceTick[] }>(
    `${BACKEND_URL}/api/market/prices/latest?limit=50`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 15000, ...config }
  );
}

export function useSignalAnalysis(symbol: string = "BTC/USDT", config?: SWRConfiguration) {
  return useSWR<SignalResult>(
    `${BACKEND_URL}/api/signals/analyze?symbol=${encodeURIComponent(symbol)}`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 60000, ...config }
  );
}

export function useMarketRegime(days: number = 30, config?: SWRConfiguration) {
  return useSWR(
    `${BACKEND_URL}/api/signals/regime?days=${days}`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 120000, ...config }
  );
}

export function useAnomalies(config?: SWRConfiguration) {
  return useSWR(
    `${BACKEND_URL}/api/signals/anomalies?type=all`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 120000, ...config }
  );
}

export function useScorecard(
  symbol: string = "BTC/USDT",
  signalType: string = "composite",
  days: number = 30,
  config?: SWRConfiguration,
) {
  return useSWR(
    `${BACKEND_URL}/api/scorecard/performance?symbol=${encodeURIComponent(symbol)}&signal_type=${signalType}&days=${days}`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 300000, ...config }
  );
}

export async function sendChatMessage(message: string): Promise<{
  reply: string;
  data: Record<string, unknown>;
  sources: string[];
  suggested_actions: string[];
}> {
  const res = await fetch(`${BACKEND_URL}/api/chat/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(`Chat error: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Paper Trading Hooks
// ---------------------------------------------------------------------------
export function usePaperPortfolio(config?: SWRConfiguration) {
  return useSWR(
    `${BACKEND_URL}/api/paper/portfolio`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 5000, ...config }
  );
}

export function usePaperOrders(limit: number = 50, config?: SWRConfiguration) {
  return useSWR(
    `${BACKEND_URL}/api/paper/orders?limit=${limit}`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 5000, ...config }
  );
}

export function usePaperPerformance(config?: SWRConfiguration) {
  return useSWR(
    `${BACKEND_URL}/api/paper/performance`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 30000, ...config }
  );
}

// ---------------------------------------------------------------------------
// Kill Switch & System Config Hooks
// ---------------------------------------------------------------------------
export interface KillSwitchStatus {
  active: boolean;
  activated_at: string | null;
  activated_by: string | null;
  reason: string | null;
}

export interface FeatureFlag {
  name: string;
  value: boolean;
  default: boolean;
  env_key: string;
}

export interface HealthReady {
  status: string;
  database: string;
  redis: string;
  scheduler: string;
  uptime_seconds: number;
  warnings?: string[];
}

export interface HealthEnv {
  status: string;
  warnings: string[];
  missing: string[];
}

export interface HealthStartup {
  status: string;
  started_at: string;
}

export interface RiskLimits {
  max_position_pct: number;
  max_drawdown_pct: number;
  max_leverage: number;
  daily_var_limit: number;
  [key: string]: unknown;
}

export function useKillSwitchStatus(config?: SWRConfiguration) {
  return useSWR<KillSwitchStatus>(
    `${BACKEND_URL}/api/paper/kill-switch/status`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 3000, ...config }
  );
}

export function useFeatureFlags(config?: SWRConfiguration) {
  return useSWR<{ flags: FeatureFlag[] } | FeatureFlag[]>(
    `${BACKEND_URL}/api/flags`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, ...config }
  );
}

export function useHealthReady(config?: SWRConfiguration) {
  return useSWR<HealthReady>(
    `${BACKEND_URL}/health/ready`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, refreshInterval: 10000, ...config }
  );
}

export function useHealthEnv(config?: SWRConfiguration) {
  return useSWR<HealthEnv>(
    `${BACKEND_URL}/health/env`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, ...config }
  );
}

export function useHealthStartup(config?: SWRConfiguration) {
  return useSWR<HealthStartup>(
    `${BACKEND_URL}/health/startup`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, ...config }
  );
}

export function useRiskLimits(config?: SWRConfiguration) {
  return useSWR<RiskLimits>(
    `${BACKEND_URL}/api/fund/risk-limits`,
    fetcher,
    { ...DEFAULT_SWR_CONFIG, ...config }
  );
}

export async function activateKillSwitch(reason: string): Promise<unknown> {
  const { authFetch } = await import("@/lib/auth");
  const res = await authFetch(
    `${BACKEND_URL}/api/paper/kill-switch/activate?reason=${encodeURIComponent(reason)}`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error(`Failed to activate kill switch: ${res.statusText}`);
  return res.json();
}

export async function deactivateKillSwitch(): Promise<unknown> {
  const { authFetch } = await import("@/lib/auth");
  const res = await authFetch(
    `${BACKEND_URL}/api/paper/kill-switch/deactivate`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error(`Failed to deactivate kill switch: ${res.statusText}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Mutation helpers (non-SWR)
// ---------------------------------------------------------------------------
export async function createAlert(payload: {
  name: string;
  enabled?: boolean;
  conditions: {
    categories?: string[];
    min_urgency?: string;
    min_relevance?: number;
    keywords?: string[];
  };
  channels: {
    webhook_url?: string;
    email?: string;
  };
}): Promise<{ id: string; status: string }> {
  const res = await fetch(`${BACKEND_URL}/alerts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to create alert: ${res.statusText}`);
  return res.json();
}

export async function deleteAlert(id: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/alerts/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete alert: ${res.statusText}`);
}

export async function toggleAlert(id: string, enabled: boolean): Promise<void> {
  await fetch(`${BACKEND_URL}/alerts/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
}

export async function seedDefaultSources(): Promise<void> {
  await fetch(`${BACKEND_URL}/sources/seed-defaults`, { method: "POST" });
}

export async function triggerScrape(): Promise<void> {
  await fetch(`${BACKEND_URL}/scrape/trigger`, { method: "POST" });
}

export async function testWebhook(url: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BACKEND_URL}/webhooks/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Utility: strip HTML from text
// ---------------------------------------------------------------------------
export function stripHtml(html: string): string {
  if (typeof window !== "undefined") {
    const doc = new DOMParser().parseFromString(html, "text/html");
    return doc.body.textContent || "";
  }
  // SSR fallback
  return html.replace(/<[^>]*>/g, "");
}

// ---------------------------------------------------------------------------
// Utility: time ago
// ---------------------------------------------------------------------------
export function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  // Normalize: backend may send "2026-03-29 23:57:11" (no T, no TZ)
  // or ISO with +00:00 offset
  let normalized = dateStr.replace(" ", "T");
  // Only append Z if no timezone indicator present
  if (!/([Z]|[+-]\d{2}:?\d{2})$/i.test(normalized)) normalized += "Z";
  const ts = new Date(normalized).getTime();
  if (isNaN(ts)) return "";
  const diff = Date.now() - ts;
  if (diff < 0) return "just now";
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}
