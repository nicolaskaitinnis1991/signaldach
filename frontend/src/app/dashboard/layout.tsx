"use client";

import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { I18nProvider } from "@/lib/i18n";
import { ThemeProvider } from "@/lib/theme";
import { ThemeToggle } from "@/components/ThemeToggle";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <ThemeProvider>
    <I18nProvider>
      <div className="flex h-screen bg-slate-950 dark:bg-slate-950 light:bg-white">
        {/* Mobile overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/60 z-40 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar — hidden on mobile unless toggled */}
        <div
          className={`fixed inset-y-0 left-0 z-50 transform transition-transform duration-200 ease-in-out md:relative md:translate-x-0 ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <Sidebar onNavigate={() => setSidebarOpen(false)} />
        </div>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          {/* Mobile header with hamburger */}
          <div className="sticky top-0 z-30 bg-slate-950/90 backdrop-blur-sm border-b border-slate-800 px-4 py-3 md:hidden">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarOpen(true)}
                className="p-2 rounded-lg hover:bg-slate-800 text-slate-300 transition-colors"
                aria-label="Open navigation menu"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                </svg>
              </button>
              <h1 className="text-lg font-bold text-white flex-1">
                Signal<span className="text-blue-400">DACH</span>
              </h1>
              <ThemeToggle />
            </div>
          </div>
          {/* Theme toggle in header */}
          <div className="hidden md:flex justify-end px-8 pt-4">
            <ThemeToggle />
          </div>
          <div className="max-w-5xl mx-auto p-4 md:p-8 md:pt-2">{children}</div>
        </main>
      </div>
    </I18nProvider>
    </ThemeProvider>
  );
}
