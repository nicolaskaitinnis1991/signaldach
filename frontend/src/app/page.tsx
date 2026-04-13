"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BACKEND_URL } from "@/lib/api";

function LivePulse() {
  return (
    <span className="relative flex h-2 w-2">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
    </span>
  );
}

function LiveStats() {
  const [stats, setStats] = useState<{
    total: number;
    sources: number;
    breaking: number;
    sentiment: number;
    regulation: number;
  } | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [analyticsRes, sourcesRes] = await Promise.all([
          fetch(`${BACKEND_URL}/analytics?days=7`).then((r) => r.json()),
          fetch(`${BACKEND_URL}/sources`).then((r) => r.json()),
        ]);
        setStats({
          total: analyticsRes.summary?.total_items || 0,
          sources: sourcesRes.sources?.length || 0,
          breaking: analyticsRes.summary?.breaking_count || 0,
          sentiment: analyticsRes.summary?.avg_sentiment || 0,
          regulation: analyticsRes.by_category?.find((c: { category: string }) => c.category === "regulation")?.count || 0,
        });
      } catch {
        // Backend not running
      }
    }
    load();
    const interval = setInterval(load, 60000);
    return () => clearInterval(interval);
  }, []);

  if (!stats) return null;

  const items = [
    { value: stats.total.toLocaleString(), label: "Signals Tracked", color: "text-white" },
    { value: stats.sources, label: "Live Sources", color: "text-blue-400" },
    { value: stats.regulation, label: "Regulatory Events", color: "text-purple-400" },
    { value: stats.breaking, label: "Breaking Alerts", color: "text-red-400" },
    {
      value: stats.sentiment > 0 ? "Bullish" : stats.sentiment < -0.1 ? "Bearish" : "Neutral",
      label: "Market Sentiment",
      color: stats.sentiment > 0 ? "text-green-400" : stats.sentiment < -0.1 ? "text-red-400" : "text-amber-400",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 max-w-4xl mx-auto mb-16">
      {items.map((item) => (
        <div key={item.label} className="text-center p-4 bg-white/5 border border-white/10 rounded-xl backdrop-blur-sm">
          <p className={`text-2xl font-bold ${item.color}`}>{item.value}</p>
          <p className="text-[11px] text-slate-400 mt-1">{item.label}</p>
        </div>
      ))}
    </div>
  );
}

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-blue-950 text-white">
      {/* Subtle grid background */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(59,130,246,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(59,130,246,0.03)_1px,transparent_1px)] bg-[size:60px_60px]" />

      <div className="relative max-w-6xl mx-auto px-8 py-12">
        {/* Nav */}
        <nav className="flex items-center justify-between mb-24">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
              </svg>
            </div>
            <h1 className="text-xl font-bold tracking-tight">
              Signal<span className="text-blue-400">DACH</span>
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20">
              <LivePulse />
              <span className="text-xs text-green-400 font-medium">Live</span>
            </div>
            <Link
              href="/dashboard/executive"
              className="px-5 py-2.5 bg-blue-600 rounded-lg text-sm font-semibold hover:bg-blue-500 transition-all duration-200 hover:shadow-lg hover:shadow-blue-500/25"
            >
              Open Dashboard
            </Link>
          </div>
        </nav>

        {/* Hero */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 mb-6">
            <span className="text-xs font-semibold text-blue-400 tracking-wider uppercase">
              AI-Powered Market Intelligence
            </span>
          </div>
          <h2 className="text-5xl sm:text-6xl font-extrabold leading-[1.1] mb-6 tracking-tight">
            Crypto Intelligence
            <br />
            <span className="bg-gradient-to-r from-blue-400 via-blue-500 to-purple-500 bg-clip-text text-transparent">
              for the DACH Region
            </span>
          </h2>
          <p className="text-lg text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            Real-time regulatory tracking from BaFin and FINMA. AI-powered market analysis.
            Institutional-grade intelligence for crypto funds operating in Germany, Austria, and Switzerland.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link
              href="/dashboard/executive"
              className="px-8 py-3.5 bg-blue-600 rounded-xl text-base font-semibold hover:bg-blue-500 transition-all duration-200 hover:shadow-xl hover:shadow-blue-500/25 hover:-translate-y-0.5"
            >
              Launch Dashboard
            </Link>
            <Link
              href="#features"
              className="px-8 py-3.5 bg-white/5 border border-white/10 rounded-xl text-base font-semibold hover:bg-white/10 transition-all duration-200"
            >
              Learn More
            </Link>
          </div>
        </div>

        {/* Live Stats */}
        <LiveStats />

        {/* Features */}
        <div id="features" className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-24">
          {[
            {
              icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0012 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75z" />
                </svg>
              ),
              title: "Regulation Tracking",
              desc: "BaFin, FINMA, MiCA, ESMA. Real-time monitoring of every regulatory change across DE, CH, and EU.",
              color: "text-purple-400",
              border: "border-purple-500/20 hover:border-purple-500/40",
            },
            {
              icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              ),
              title: "Competitor Intel",
              desc: "Track fund launches, license approvals, AuM reports, and institutional moves in the DACH region.",
              color: "text-amber-400",
              border: "border-amber-500/20 hover:border-amber-500/40",
            },
            {
              icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" />
                </svg>
              ),
              title: "AI Sentiment",
              desc: "GPT-4o powered analysis of 13+ sources. Sentiment scoring, entity extraction, trend detection.",
              color: "text-green-400",
              border: "border-green-500/20 hover:border-green-500/40",
            },
            {
              icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
                </svg>
              ),
              title: "Smart Alerts",
              desc: "Breaking event alerts via webhook and email. Custom rules, keyword triggers, urgency filters.",
              color: "text-red-400",
              border: "border-red-500/20 hover:border-red-500/40",
            },
          ].map((f) => (
            <div
              key={f.title}
              className={`bg-white/[0.03] border ${f.border} rounded-xl p-6 transition-all duration-300 hover:bg-white/[0.06]`}
            >
              <div className={`${f.color} mb-4`}>{f.icon}</div>
              <h3 className="font-bold text-white mb-2">{f.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>

        {/* Data Sources */}
        <div className="text-center mb-24">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-6">
            Powered by 13+ Data Sources
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            {[
              "BaFin", "FINMA", "CoinDesk", "CoinTelegraph", "The Block",
              "Decrypt", "BTC-ECHO", "CoinGecko", "DeFi Llama",
              "Crypto Valley Journal", "Bitcoin Magazine",
            ].map((source) => (
              <span
                key={source}
                className="px-4 py-2 bg-white/[0.03] border border-white/[0.06] rounded-lg text-sm text-slate-400 hover:text-white hover:border-white/20 transition-colors duration-200"
              >
                {source}
              </span>
            ))}
          </div>
        </div>

        {/* Pricing */}
        <div className="mb-24">
          <div className="text-center mb-10">
            <h3 className="text-3xl font-bold mb-3">Simple Pricing</h3>
            <p className="text-slate-400">Start free. Scale when you need to.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
            <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-7">
              <h4 className="font-bold text-lg mb-1">Starter</h4>
              <p className="text-4xl font-extrabold mb-1">
                {"\u20AC"}0<span className="text-sm font-normal text-slate-500">/mo</span>
              </p>
              <p className="text-xs text-slate-500 mb-6">Perfect for exploring</p>
              <ul className="space-y-3 text-sm text-slate-300 mb-8">
                {["5 sources", "Daily updates", "Basic analytics", "1 alert rule"].map((f) => (
                  <li key={f} className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
                    {f}
                  </li>
                ))}
              </ul>
              <Link href="/dashboard/executive" className="block text-center px-4 py-2.5 bg-white/10 rounded-xl text-sm font-semibold hover:bg-white/20 transition-colors">
                Get Started
              </Link>
            </div>

            <div className="bg-blue-600/10 border-2 border-blue-500/50 rounded-2xl p-7 relative shadow-lg shadow-blue-500/10">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 bg-blue-500 text-white text-xs font-bold rounded-full">
                MOST POPULAR
              </div>
              <h4 className="font-bold text-lg mb-1">Professional</h4>
              <p className="text-4xl font-extrabold mb-1">
                {"\u20AC"}99<span className="text-sm font-normal text-slate-500">/mo</span>
              </p>
              <p className="text-xs text-slate-500 mb-6">For serious traders</p>
              <ul className="space-y-3 text-sm text-slate-300 mb-8">
                {["All 13+ sources", "Real-time (30s refresh)", "AI-powered reports", "Unlimited alerts", "Webhook + Email", "Trend detection"].map((f) => (
                  <li key={f} className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
                    {f}
                  </li>
                ))}
              </ul>
              <Link href="/dashboard/executive" className="block text-center px-4 py-2.5 bg-blue-600 rounded-xl text-sm font-semibold hover:bg-blue-500 transition-all">
                Start Free Trial
              </Link>
            </div>

            <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-7">
              <h4 className="font-bold text-lg mb-1">Enterprise</h4>
              <p className="text-4xl font-extrabold mb-1">Custom</p>
              <p className="text-xs text-slate-500 mb-6">For funds & institutions</p>
              <ul className="space-y-3 text-sm text-slate-300 mb-8">
                {["Everything in Pro", "Custom sources", "REST API access", "White-label option", "SLA guarantee", "Dedicated support"].map((f) => (
                  <li key={f} className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
                    {f}
                  </li>
                ))}
              </ul>
              <a href="mailto:enterprise@signaldach.com" className="block text-center px-4 py-2.5 bg-white/10 rounded-xl text-sm font-semibold hover:bg-white/20 transition-colors">
                Contact Sales
              </a>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="border-t border-white/5 pt-8 pb-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 bg-blue-600 rounded flex items-center justify-center">
                <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                </svg>
              </div>
              <span className="text-sm font-semibold text-slate-400">
                Signal<span className="text-blue-400">DACH</span>
              </span>
            </div>
            <div className="flex items-center gap-6 text-xs text-slate-500">
              <Link href="/impressum" className="hover:text-white transition-colors">Impressum</Link>
              <Link href="/datenschutz" className="hover:text-white transition-colors">Datenschutz</Link>
              <Link href="/agb" className="hover:text-white transition-colors">AGB</Link>
            </div>
            <p className="text-xs text-slate-600">&copy; 2026 SignalDACH</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
