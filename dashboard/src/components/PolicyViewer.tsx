"use client";

import type { Policy } from "@/lib/types";

interface PolicyViewerProps {
  policies: Policy[];
}

export default function PolicyViewer({ policies }: PolicyViewerProps) {
  if (policies.length === 0) {
    return <p className="text-gray-500">No policies loaded.</p>;
  }

  return (
    <div className="space-y-4">
      {policies.map((p) => (
        <div
          key={p.name}
          className={`border rounded-lg p-4 ${
            p.deny
              ? "border-red-500/30 bg-red-950/10"
              : "border-gray-800 bg-gray-900"
          }`}
        >
          <div className="flex items-center gap-3 mb-2">
            <span
              className={`text-xs px-2 py-0.5 rounded font-medium ${
                p.deny
                  ? "bg-red-900/40 text-red-400"
                  : "bg-green-900/40 text-green-400"
              }`}
            >
              {p.deny ? "DENY" : "ALLOW"}
            </span>
            <h3 className="font-medium text-gray-200">{p.name}</h3>
            <span className="text-xs text-gray-500 ml-auto">
              priority: {p.priority}
            </span>
          </div>
          {p.description && (
            <p className="text-xs text-gray-500 mb-3">{p.description}</p>
          )}
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <h4 className="text-gray-500 uppercase tracking-wider mb-1">
                Conditions
              </h4>
              {p.conditions.map((c, i) => (
                <div key={i} className="font-mono text-gray-400">
                  {c.requester} @ {c.environment} / {c.task}
                </div>
              ))}
            </div>
            {!p.deny && p.grants.length > 0 && (
              <div>
                <h4 className="text-gray-500 uppercase tracking-wider mb-1">
                  Grants
                </h4>
                {p.grants.map((g, i) => (
                  <div key={i} className="font-mono text-gray-400">
                    {g.secret_ref}{" "}
                    <span className="text-gray-600">
                      ({g.ttl_seconds}s, x{g.max_uses})
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
