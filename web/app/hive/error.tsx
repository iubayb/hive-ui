"use client"
export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4 p-6">
      <p className="text-zinc-400 text-sm font-mono">Failed to load hive status</p>
      <p className="text-zinc-600 text-xs font-mono">{error.message}</p>
      <button onClick={reset} className="px-4 py-2 bg-zinc-800 text-zinc-300 rounded text-sm hover:bg-zinc-700">
        Retry
      </button>
    </div>
  )
}
