"use client";

import { useEffect, useState } from "react";
import type { SSHKey } from "@/lib/types";
import { fetchJson } from "@/lib/api";

export default function SSHPage() {
  const [keys, setKeys] = useState<SSHKey[]>([]);

  useEffect(() => {
    fetchJson<SSHKey[]>("/ssh/keys").then(setKeys).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100 mb-1">SSH Keys</h2>
        <p className="text-sm text-gray-500">
          Registered SSH keys with policy enforcement and usage tracking.
          Extends 1Password's SSH agent with an approval layer.
        </p>
      </div>

      {keys.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No SSH keys registered. Use the API to register keys:
          <pre className="mt-3 bg-gray-900 border border-gray-800 rounded p-3 text-xs text-left inline-block">
{`POST /ssh/keys
{
  "name": "dev-deploy-key",
  "fingerprint": "SHA256:abc123...",
  "key_type": "ed25519",
  "has_passphrase": true,
  "description": "Development deploy key"
}`}
          </pre>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500 text-left">
                <th className="pb-2 pr-4">Name</th>
                <th className="pb-2 pr-4">Type</th>
                <th className="pb-2 pr-4">Fingerprint</th>
                <th className="pb-2 pr-4">Passphrase</th>
                <th className="pb-2 pr-4">Last Used</th>
                <th className="pb-2 pr-4">Used By</th>
                <th className="pb-2">Accesses</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr
                  key={k.id}
                  className="border-b border-gray-800/50 hover:bg-gray-900/50"
                >
                  <td className="py-2 pr-4 font-mono text-gray-200">
                    {k.name}
                  </td>
                  <td className="py-2 pr-4 text-xs text-gray-400">
                    {k.key_type}
                  </td>
                  <td className="py-2 pr-4 font-mono text-xs text-gray-500">
                    {k.fingerprint.slice(0, 20)}...
                  </td>
                  <td className="py-2 pr-4">
                    {k.has_passphrase ? (
                      <span className="text-green-400 text-xs">Yes</span>
                    ) : (
                      <span className="text-red-400 text-xs font-medium">
                        NO
                      </span>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-xs text-gray-500">
                    {k.last_used_at
                      ? new Date(k.last_used_at).toLocaleString()
                      : "Never"}
                  </td>
                  <td className="py-2 pr-4 text-xs text-gray-400">
                    {k.last_used_by || "—"}
                  </td>
                  <td className="py-2 text-xs">{k.access_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
