"use client";

import { useEffect, useState } from "react";
import SecretRequestForm from "@/components/SecretRequestForm";
import type { AuditLog } from "@/lib/types";
import { fetchJson } from "@/lib/api";

export default function AgentsPage() {
  const [recentGrants, setRecentGrants] = useState<AuditLog[]>([]);

  useEffect(() => {
    fetchJson<AuditLog[]>("/audit/logs", { action: "granted", limit: "20" })
      .then(setRecentGrants)
      .catch(() => {});
  }, []);

  // Derive unique agent sessions from recent grants
  const agentSessions = new Map<
    string,
    { count: number; lastSeen: string; environment: string }
  >();
  for (const log of recentGrants) {
    if (!log.requester.startsWith("agent:")) continue;
    const existing = agentSessions.get(log.requester);
    if (!existing) {
      agentSessions.set(log.requester, {
        count: 1,
        lastSeen: log.timestamp,
        environment: log.environment,
      });
    } else {
      existing.count += 1;
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100 mb-1">
          Agent Sessions
        </h2>
        <p className="text-sm text-gray-500">
          Active AI agents and their credential grants
        </p>
      </div>

      <div className="grid gap-3">
        {agentSessions.size === 0 ? (
          <div className="text-gray-500 text-center py-8">
            No agent activity yet. Use the form below or run the demo script.
          </div>
        ) : (
          Array.from(agentSessions.entries()).map(([name, info]) => (
            <div
              key={name}
              className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex items-center justify-between"
            >
              <div>
                <p className="font-mono text-sm text-gray-200">{name}</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {info.environment} — {info.count} grant
                  {info.count !== 1 ? "s" : ""}
                </p>
              </div>
              <p className="text-xs text-gray-500">
                Last active:{" "}
                {new Date(info.lastSeen).toLocaleTimeString()}
              </p>
            </div>
          ))
        )}
      </div>

      <div>
        <h3 className="text-sm font-medium text-gray-400 mb-3">
          Manual Agent Request
        </h3>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 max-w-2xl">
          <SecretRequestForm />
        </div>
      </div>
    </div>
  );
}
