export default function DashboardLoading() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div>
        <div className="h-8 w-48 bg-slate-800 rounded animate-pulse" />
        <div className="h-4 w-64 bg-slate-800/50 rounded animate-pulse mt-2" />
      </div>

      {/* Cards skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <div className="h-3 w-16 bg-slate-800 rounded animate-pulse" />
            <div className="h-8 w-32 bg-slate-800 rounded animate-pulse mt-3" />
            <div className="h-4 w-20 bg-slate-800/50 rounded animate-pulse mt-2" />
          </div>
        ))}
      </div>

      {/* Content skeleton */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
        <div className="h-5 w-32 bg-slate-800 rounded animate-pulse mb-4" />
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <div className="h-4 w-16 bg-slate-800 rounded animate-pulse" />
              <div className="h-4 flex-1 bg-slate-800/50 rounded animate-pulse" />
              <div className="h-4 w-20 bg-slate-800 rounded animate-pulse" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
