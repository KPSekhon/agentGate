"use client";

import { useEffect, useState } from "react";
import AuditTable from "@/components/AuditTable";
import type { AuditLog } from "@/lib/types";
import { fetchJson } from "@/lib/api";

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [actionFilter, setActionFilter] = useState("");
  const [requesterFilter, setRequesterFilter] = useState("");

  useEffect(() => {
    const params: Record<string, string> = { limit: "100" };
    if (actionFilter) params.action = actionFilter;
    if (requesterFilter) params.requester = requesterFilter;

    fetchJson<AuditLog[]>("/audit/logs", params)
      .then(setLogs)
      .catch(() => {});

    const interval = setInterval(() => {
      fetchJson<AuditLog[]>("/audit/logs", params)
        .then(setLogs)
        .catch(() => {});
    }, 3000);
    return () => clearInterval(interval);
  }, [actionFilter, requesterFilter]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-gray-100 mb-1">Audit Logs</h2>
        <p className="text-sm text-gray-500">
          Every credential request, grant, denial, and expiry
        </p>
      </div>

      <div className="flex gap-3">
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-300 outline-none"
        >
          <option value="">All Actions</option>
          <option value="granted">Granted</option>
          <option value="denied">Denied</option>
          <option value="released">Released</option>
          <option value="expired">Expired</option>
        </select>
        <input
          placeholder="Filter by requester..."
          value={requesterFilter}
          onChange={(e) => setRequesterFilter(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-300 outline-none flex-1 max-w-xs"
        />
      </div>

      <AuditTable logs={logs} />
    </div>
  );
}
