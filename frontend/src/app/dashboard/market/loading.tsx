export default function MarketLoading() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div>
        <div className="h-8 w-48 bg-slate-800 rounded animate-pulse" />
        <div className="h-4 w-64 bg-slate-800/50 rounded animate-pulse mt-2" />
      </div>

      {/* 4 metric cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <div className="h-3 w-16 bg-slate-800 rounded animate-pulse" />
            <div className="h-8 w-32 bg-slate-800 rounded animate-pulse mt-3" />
            <div className="h-4 w-20 bg-slate-800/50 rounded animate-pulse mt-2" />
          </div>
        ))}
      </div>

      {/* Large chart area */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
        <div className="h-5 w-40 bg-slate-800 rounded animate-pulse mb-4" />
        <div className="h-64 w-full bg-slate-800/30 rounded-lg animate-pulse" />
      </div>

      {/* Table skeleton */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
        <div className="h-5 w-32 bg-slate-800 rounded animate-pulse mb-4" />
        {/* Table header */}
        <div className="flex items-center gap-4 pb-3 border-b border-slate-700 mb-3">
          <div className="h-3 w-20 bg-slate-700 rounded animate-pulse" />
          <div className="h-3 w-24 bg-slate-700 rounded animate-pulse" />
          <div className="h-3 flex-1 bg-slate-700 rounded animate-pulse" />
          <div className="h-3 w-20 bg-slate-700 rounded animate-pulse" />
          <div className="h-3 w-16 bg-slate-700 rounded animate-pulse" />
        </div>
        {/* Table rows */}
        {[...Array(8)].map((_, i) => (
          <div key={i} className="flex items-center gap-4 py-2.5">
            <div className="h-4 w-20 bg-slate-800 rounded animate-pulse" />
            <div className="h-4 w-24 bg-slate-800/50 rounded animate-pulse" />
            <div className="h-4 flex-1 bg-slate-800/30 rounded animate-pulse" />
            <div className="h-4 w-20 bg-slate-800/50 rounded animate-pulse" />
            <div className="h-4 w-16 bg-slate-800 rounded animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}
