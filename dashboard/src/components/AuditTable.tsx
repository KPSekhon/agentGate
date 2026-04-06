"use client";

import type { AuditLog } from "@/lib/types";
import AnomalyBadge from "./AnomalyBadge";

const actionColors: Record<string, string> = {
  granted: "text-green-400",
  denied: "text-red-400",
  released: "text-blue-400",
  expired: "text-yellow-400",
};

function maskRef(ref: string): string {
  // Show vault/item but not field details
  const parts = ref.replace("op://", "").split("/");
  if (parts.length >= 2) return `${parts[0]}/${parts[1]}`;
  return ref;
}

interface AuditTableProps {
  logs: AuditLog[];
}

export default function AuditTable({ logs }: AuditTableProps) {
  if (logs.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        No audit entries yet. Run the demo to generate some.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800 text-gray-500 text-left">
            <th className="pb-2 pr-4">Time</th>
            <th className="pb-2 pr-4">Action</th>
            <th className="pb-2 pr-4">Requester</th>
            <th className="pb-2 pr-4">Secret</th>
            <th className="pb-2 pr-4">Environment</th>
            <th className="pb-2 pr-4">Policy</th>
            <th className="pb-2 pr-4">TTL</th>
            <th className="pb-2">Anomaly</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr
              key={log.id}
              className={`border-b border-gray-800/50 hover:bg-gray-900/50 ${
                log.anomaly_score > 0.5 ? "bg-amber-950/20" : ""
              }`}
            >
              <td className="py-2 pr-4 text-gray-400 font-mono text-xs">
                {new Date(log.timestamp).toLocaleTimeString()}
              </td>
              <td className={`py-2 pr-4 font-medium uppercase text-xs ${actionColors[log.action] ?? "text-gray-400"}`}>
                {log.action}
              </td>
              <td className="py-2 pr-4 font-mono text-xs">{log.requester}</td>
              <td className="py-2 pr-4 font-mono text-xs text-gray-300">
                {maskRef(log.secret_ref)}
              </td>
              <td className="py-2 pr-4 text-xs">{log.environment}</td>
              <td className="py-2 pr-4 text-xs text-gray-400">
                {log.policy_name || "—"}
              </td>
              <td className="py-2 pr-4 text-xs text-gray-500">
                {log.ttl_seconds > 0 ? `${log.ttl_seconds}s` : "—"}
              </td>
              <td className="py-2">
                <AnomalyBadge score={log.anomaly_score} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
