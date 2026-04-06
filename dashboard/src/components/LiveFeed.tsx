"use client";

import { useAuditWebSocket } from "@/lib/useWebSocket";
import AnomalyBadge from "./AnomalyBadge";

const actionColors: Record<string, string> = {
  granted: "text-green-400",
  denied: "text-red-400",
  released: "text-blue-400",
  expired: "text-yellow-400",
};

export default function LiveFeed() {
  const { entries, connected } = useAuditWebSocket();

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-gray-300">Live Feed</h3>
        <span
          className={`text-xs flex items-center gap-1.5 ${
            connected ? "text-green-400" : "text-red-400"
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              connected ? "bg-green-400 animate-pulse" : "bg-red-400"
            }`}
          />
          {connected ? "Connected" : "Disconnected"}
        </span>
      </div>
      <div className="space-y-1 max-h-64 overflow-y-auto font-mono text-xs">
        {entries.length === 0 ? (
          <p className="text-gray-600 py-4 text-center">
            Waiting for events...
          </p>
        ) : (
          entries.map((e) => (
            <div
              key={e.id}
              className={`flex items-center gap-2 py-1 px-2 rounded ${
                e.anomaly_score > 0.5 ? "bg-amber-950/30" : "hover:bg-gray-800/50"
              }`}
            >
              <span className="text-gray-500 w-16">
                {new Date(e.timestamp).toLocaleTimeString()}
              </span>
              <span
                className={`w-16 uppercase font-medium ${
                  actionColors[e.action] ?? "text-gray-400"
                }`}
              >
                {e.action}
              </span>
              <span className="text-gray-300 flex-1 truncate">
                {e.requester}
              </span>
              <AnomalyBadge score={e.anomaly_score} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
