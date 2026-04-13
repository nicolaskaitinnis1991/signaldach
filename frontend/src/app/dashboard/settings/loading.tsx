export default function SettingsLoading() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div>
        <div className="h-8 w-40 bg-slate-800 rounded animate-pulse" />
        <div className="h-4 w-56 bg-slate-800/50 rounded animate-pulse mt-2" />
      </div>

      {/* Kill Switch card skeleton */}
      <div className="bg-slate-900 rounded-xl border border-red-900/30 p-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="h-6 w-32 bg-slate-800 rounded animate-pulse" />
            <div className="h-4 w-48 bg-slate-800/50 rounded animate-pulse mt-2" />
          </div>
          <div className="h-10 w-32 bg-slate-800 rounded-lg animate-pulse" />
        </div>
      </div>

      {/* Feature Flags skeleton */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
        <div className="h-5 w-32 bg-slate-800 rounded animate-pulse mb-4" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
              <div className="h-4 w-28 bg-slate-800 rounded animate-pulse" />
              <div className="h-6 w-12 bg-slate-800 rounded-full animate-pulse" />
            </div>
          ))}
        </div>
      </div>

      {/* System Health skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <div className="h-4 w-20 bg-slate-800 rounded animate-pulse" />
            <div className="h-8 w-24 bg-slate-800 rounded animate-pulse mt-3" />
            <div className="h-3 w-16 bg-slate-800/50 rounded animate-pulse mt-2" />
          </div>
        ))}
      </div>
    </div>
  );
}
