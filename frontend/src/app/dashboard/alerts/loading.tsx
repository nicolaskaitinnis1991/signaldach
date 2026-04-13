export default function AlertsLoading() {
  return (
    <div className="space-y-6">
      {/* Header + button */}
      <div className="flex items-center justify-between">
        <div>
          <div className="h-8 w-32 bg-slate-800 rounded animate-pulse" />
          <div className="h-4 w-56 bg-slate-800/50 rounded animate-pulse mt-2" />
        </div>
        <div className="h-10 w-36 bg-slate-800 rounded-lg animate-pulse" />
      </div>

      {/* 4 alert card skeletons */}
      <div className="space-y-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-slate-800 animate-pulse" />
                <div>
                  <div className="h-5 w-40 bg-slate-800 rounded animate-pulse" />
                  <div className="h-3 w-24 bg-slate-800/50 rounded animate-pulse mt-1.5" />
                </div>
              </div>
              <div className="h-6 w-16 bg-slate-800 rounded-full animate-pulse" />
            </div>
            <div className="h-3 w-full bg-slate-800/30 rounded animate-pulse" />
            <div className="h-3 w-3/4 bg-slate-800/30 rounded animate-pulse mt-1.5" />
            <div className="flex items-center gap-3 mt-4">
              <div className="h-3 w-20 bg-slate-800/50 rounded animate-pulse" />
              <div className="h-3 w-28 bg-slate-800/50 rounded animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
