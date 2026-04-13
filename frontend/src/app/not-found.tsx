import Link from "next/link";

export default function NotFound() {
  return (
    <div
      role="alert"
      className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-center px-4"
    >
      <p className="text-8xl font-bold text-slate-800 mb-4">404</p>
      <h1 className="text-2xl font-bold text-white mb-2">Page not found</h1>
      <p className="text-sm text-slate-400 mb-8 max-w-md">
        The page you are looking for does not exist or has been moved.
      </p>
      <Link
        href="/dashboard"
        className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
      >
        Back to Dashboard
      </Link>
      <p className="text-xs text-slate-600 mt-12">
        SignalDACH - AI-Powered Market Intelligence
      </p>
    </div>
  );
}
