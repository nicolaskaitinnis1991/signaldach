export default function SignalsLoading() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div>
        <div className="h-8 w-48 bg-slate-800 rounded animate-pulse" />
        <div className="h-4 w-72 bg-slate-800/50 rounded animate-pulse mt-2" />
      </div>

      {/* Signal strength indicator */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-5">
        <div className="h-4 w-36 bg-slate-800 rounded animate-pulse mb-3" />
        <div className="h-6 w-full bg-slate-800/30 rounded-full animate-pulse" />
      </div>

      {/* 3 metric cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <div className="h-3 w-20 bg-slate-800 rounded animate-pulse" />
            <div className="h-8 w-28 bg-slate-800 rounded animate-pulse mt-3" />
            <div className="h-4 w-16 bg-slate-800/50 rounded animate-pulse mt-2" />
          </div>
        ))}
      </div>

      {/* Radar chart placeholder + Agent analysis boxes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Radar chart */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 p-5 flex flex-col items-center">
          <div className="h-5 w-32 bg-slate-800 rounded animate-pulse mb-4 self-start" />
          <div className="w-48 h-48 rounded-full bg-slate-800/30 animate-pulse" />
        </div>

        {/* Agent analysis boxes */}
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-slate-900 rounded-xl border border-slate-700 p-4">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-8 h-8 rounded-lg bg-slate-800 animate-pulse" />
                <div className="h-4 w-28 bg-slate-800 rounded animate-pulse" />
              </div>
              <div className="h-3 w-full bg-slate-800/30 rounded animate-pulse" />
              <div className="h-3 w-3/4 bg-slate-800/30 rounded animate-pulse mt-1.5" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
