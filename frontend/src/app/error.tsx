"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-center px-4"
    >
      <div className="w-20 h-20 rounded-2xl bg-red-500/10 flex items-center justify-center mb-8">
        <svg className="w-10 h-10 text-red-400" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
        </svg>
      </div>
      <h1 className="text-3xl font-bold text-white mb-2">Something went wrong</h1>
      <p className="text-sm text-slate-400 mb-2 max-w-md">
        An unexpected error occurred in SignalDACH. Our team has been notified.
      </p>
      <p className="text-xs text-slate-500 mb-8 font-mono">
        {error.digest ? `Error ID: ${error.digest}` : ""}
      </p>
      <div className="flex items-center gap-4">
        <button
          onClick={reset}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          Try again
        </button>
        <a
          href="/dashboard"
          className="px-6 py-2.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-medium transition-colors"
        >
          Go to Dashboard
        </a>
      </div>
      <p className="text-xs text-slate-600 mt-12">
        SignalDACH - AI-Powered Market Intelligence
      </p>
    </div>
  );
}
