export default function PaperTradingLoading() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div>
        <div className="flex items-center gap-3">
          <div className="h-8 w-48 bg-slate-800 rounded animate-pulse" />
          <div className="h-6 w-24 bg-orange-500/10 rounded animate-pulse" />
        </div>
        <div className="h-4 w-72 bg-slate-800/50 rounded animate-pulse mt-2" />
      </div>

      {/* Portfolio summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <div className="h-3 w-20 bg-slate-800 rounded animate-pulse" />
            <div className="h-8 w-32 bg-slate-800 rounded animate-pulse mt-3" />
          </div>
        ))}
      </div>

      {/* Order form skeleton */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
        <div className="h-5 w-28 bg-slate-800 rounded animate-pulse mb-4" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i}>
              <div className="h-3 w-16 bg-slate-800/50 rounded animate-pulse mb-1" />
              <div className="h-10 bg-slate-800 rounded-lg animate-pulse" />
            </div>
          ))}
        </div>
      </div>

      {/* Positions table skeleton */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
        <div className="h-5 w-36 bg-slate-800 rounded animate-pulse mb-4" />
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <div className="h-4 w-20 bg-slate-800 rounded animate-pulse" />
              <div className="h-4 flex-1 bg-slate-800/50 rounded animate-pulse" />
              <div className="h-4 w-24 bg-slate-800 rounded animate-pulse" />
            </div>
          ))}
        </div>
      </div>

      {/* Order history skeleton */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
        <div className="h-5 w-32 bg-slate-800 rounded animate-pulse mb-4" />
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <div className="h-4 w-28 bg-slate-800 rounded animate-pulse" />
              <div className="h-4 w-16 bg-slate-800/50 rounded animate-pulse" />
              <div className="h-4 flex-1 bg-slate-800/50 rounded animate-pulse" />
              <div className="h-4 w-16 bg-slate-800 rounded animate-pulse" />
            </div>
          ))}
        </div>
      </div>

      {/* Performance cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <div className="h-3 w-20 bg-slate-800 rounded animate-pulse" />
            <div className="h-8 w-24 bg-slate-800 rounded animate-pulse mt-3" />
          </div>
        ))}
      </div>
    </div>
  );
}
