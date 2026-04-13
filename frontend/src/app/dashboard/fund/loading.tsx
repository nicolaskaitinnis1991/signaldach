export default function FundLoading() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div>
        <div className="h-8 w-48 bg-slate-800 rounded animate-pulse" />
        <div className="h-4 w-56 bg-slate-800/50 rounded animate-pulse mt-2" />
      </div>

      {/* 4 KPI cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <div className="h-3 w-16 bg-slate-800 rounded animate-pulse" />
            <div className="h-8 w-32 bg-slate-800 rounded animate-pulse mt-3" />
            <div className="h-4 w-20 bg-slate-800/50 rounded animate-pulse mt-2" />
          </div>
        ))}
      </div>

      {/* Pie chart + Risk limits table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pie chart placeholder */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5 flex flex-col items-center">
          <div className="h-5 w-36 bg-slate-800 rounded animate-pulse mb-4 self-start" />
          <div className="w-52 h-52 rounded-full bg-slate-800/30 animate-pulse" />
          <div className="flex gap-4 mt-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-slate-800 animate-pulse" />
                <div className="h-3 w-14 bg-slate-800/50 rounded animate-pulse" />
              </div>
            ))}
          </div>
        </div>

        {/* Risk limits table */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
          <div className="h-5 w-28 bg-slate-800 rounded animate-pulse mb-4" />
          {[...Array(6)].map((_, i) => (
            <div key={i} className="flex items-center justify-between py-2.5 border-b border-slate-800 last:border-0">
              <div className="h-4 w-32 bg-slate-800 rounded animate-pulse" />
              <div className="h-4 w-20 bg-slate-800/50 rounded animate-pulse" />
              <div className="h-4 w-16 bg-slate-800 rounded animate-pulse" />
            </div>
          ))}
        </div>
      </div>

      {/* Scorecard section */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
        <div className="h-5 w-24 bg-slate-800 rounded animate-pulse mb-4" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-slate-800/30 rounded-lg p-4">
              <div className="h-3 w-20 bg-slate-800 rounded animate-pulse" />
              <div className="h-10 w-16 bg-slate-800 rounded animate-pulse mt-3 mx-auto" />
              <div className="h-3 w-24 bg-slate-800/50 rounded animate-pulse mt-2" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
