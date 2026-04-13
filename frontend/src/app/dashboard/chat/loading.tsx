export default function ChatLoading() {
  return (
    <div className="flex flex-col h-[calc(100vh-12rem)]">
      {/* Chat header */}
      <div className="flex items-center gap-3 pb-4 border-b border-slate-700 mb-4">
        <div className="w-10 h-10 rounded-full bg-slate-800 animate-pulse" />
        <div>
          <div className="h-5 w-32 bg-slate-800 rounded animate-pulse" />
          <div className="h-3 w-20 bg-slate-800/50 rounded animate-pulse mt-1.5" />
        </div>
      </div>

      {/* Message area */}
      <div className="flex-1 space-y-6 overflow-hidden">
        {/* AI message (left) */}
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-800 animate-pulse shrink-0" />
          <div className="bg-slate-900 rounded-xl border border-slate-700 p-4 max-w-[70%]">
            <div className="h-3 w-64 bg-slate-800 rounded animate-pulse" />
            <div className="h-3 w-48 bg-slate-800/50 rounded animate-pulse mt-2" />
            <div className="h-3 w-56 bg-slate-800/30 rounded animate-pulse mt-2" />
          </div>
        </div>

        {/* User message (right) */}
        <div className="flex items-start gap-3 justify-end">
          <div className="bg-blue-600/20 rounded-xl border border-blue-500/20 p-4 max-w-[70%]">
            <div className="h-3 w-40 bg-blue-500/20 rounded animate-pulse" />
            <div className="h-3 w-32 bg-blue-500/10 rounded animate-pulse mt-2" />
          </div>
          <div className="w-8 h-8 rounded-full bg-slate-800 animate-pulse shrink-0" />
        </div>

        {/* AI message (left) */}
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-800 animate-pulse shrink-0" />
          <div className="bg-slate-900 rounded-xl border border-slate-700 p-4 max-w-[70%]">
            <div className="h-3 w-72 bg-slate-800 rounded animate-pulse" />
            <div className="h-3 w-52 bg-slate-800/50 rounded animate-pulse mt-2" />
          </div>
        </div>
      </div>

      {/* Input box */}
      <div className="mt-4 pt-4 border-t border-slate-700">
        <div className="flex items-center gap-3">
          <div className="flex-1 h-12 bg-slate-900 rounded-xl border border-slate-700 animate-pulse" />
          <div className="w-12 h-12 bg-slate-800 rounded-xl animate-pulse" />
        </div>
      </div>
    </div>
  );
}
