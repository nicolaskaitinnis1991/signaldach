export default function AnalyticsLoading() {
  return (
    <div className="space-y-6">
      {/* Header + date picker */}
      <div className="flex items-center justify-between">
        <div>
          <div className="h-8 w-36 bg-slate-800 rounded animate-pulse" />
          <div className="h-4 w-52 bg-slate-800/50 rounded animate-pulse mt-2" />
        </div>
        <div className="h-10 w-48 bg-slate-800 rounded-lg animate-pulse" />
      </div>

      {/* 2 large chart areas */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[...Array(2)].map((_, i) => (
          <div key={i} className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <div className="h-5 w-36 bg-slate-800 rounded animate-pulse mb-4" />
            <div className="h-56 w-full bg-slate-800/30 rounded-lg animate-pulse" />
          </div>
        ))}
      </div>

      {/* Stats row (3 cards) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <div className="h-3 w-20 bg-slate-800 rounded animate-pulse" />
            <div className="h-8 w-28 bg-slate-800 rounded animate-pulse mt-3" />
            <div className="h-4 w-16 bg-slate-800/50 rounded animate-pulse mt-2" />
          </div>
        ))}
      </div>
    </div>
  );
}
