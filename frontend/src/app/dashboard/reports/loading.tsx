export default function ReportsLoading() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div>
        <div className="h-8 w-52 bg-slate-800 rounded animate-pulse" />
        <div className="h-4 w-72 bg-slate-800/50 rounded animate-pulse mt-2" />
      </div>

      {/* PDF report card skeleton */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-slate-800 rounded-lg animate-pulse" />
          <div>
            <div className="h-5 w-40 bg-slate-800 rounded animate-pulse" />
            <div className="h-3 w-56 bg-slate-800/50 rounded animate-pulse mt-2" />
          </div>
        </div>
        <div className="flex items-end gap-4">
          <div className="h-10 w-36 bg-slate-800 rounded-lg animate-pulse" />
          <div className="h-10 w-32 bg-slate-800 rounded-lg animate-pulse" />
        </div>
      </div>

      {/* Excel section title skeleton */}
      <div className="h-6 w-32 bg-slate-800 rounded animate-pulse" />

      {/* Excel cards grid skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-slate-900 rounded-xl border border-slate-700 p-5">
            <div className="h-4 w-28 bg-slate-800 rounded animate-pulse mb-3" />
            <div className="space-y-3">
              <div className="h-9 w-full bg-slate-800 rounded-lg animate-pulse" />
              <div className="h-9 w-full bg-slate-800 rounded-lg animate-pulse" />
              <div className="h-10 w-full bg-slate-800 rounded-lg animate-pulse" />
            </div>
          </div>
        ))}
      </div>

      {/* Email digest skeleton */}
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-slate-800 rounded-lg animate-pulse" />
          <div>
            <div className="h-5 w-32 bg-slate-800 rounded animate-pulse" />
            <div className="h-3 w-48 bg-slate-800/50 rounded animate-pulse mt-2" />
          </div>
        </div>
        <div className="flex gap-3">
          <div className="h-10 w-28 bg-slate-800 rounded-lg animate-pulse" />
          <div className="h-10 w-28 bg-slate-800 rounded-lg animate-pulse" />
        </div>
      </div>
    </div>
  );
}
