"use client";

import { useState } from "react";
import type { GrantResponse, SecretResponse } from "@/lib/types";

export default function SecretRequestForm() {
  const [agentName, setAgentName] = useState("demo-agent-01");
  const [environment, setEnvironment] = useState("development");
  const [task, setTask] = useState("summarize-logs");
  const [secretRef, setSecretRef] = useState(
    "op://demo-vault/api-key/credential"
  );
  const [ttl, setTtl] = useState(300);
  const [grantResult, setGrantResult] = useState<string | null>(null);
  const [exchangeResult, setExchangeResult] = useState<string | null>(null);
  const [grantId, setGrantId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState<1 | 2>(1);

  async function handleRequestGrant(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setGrantResult(null);
    setExchangeResult(null);
    setGrantId(null);
    setPhase(1);
    try {
      const res = await fetch("/api/agent/request-secret", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer demo-token-12345",
        },
        body: JSON.stringify({
          agent_name: agentName,
          environment,
          task,
          secret_ref: secretRef,
          requested_ttl: ttl,
        }),
      });
      const data = await res.json();
      setGrantResult(JSON.stringify(data, null, 2));
      if (res.ok && data.grant_id) {
        setGrantId(data.grant_id);
        setPhase(2);
      }
    } catch (err: any) {
      setGrantResult(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleExchange() {
    if (!grantId) return;
    setLoading(true);
    setExchangeResult(null);
    try {
      const res = await fetch("/api/agent/exchange", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer demo-token-12345",
        },
        body: JSON.stringify({ grant_id: grantId }),
      });
      const data = await res.json();
      setExchangeResult(JSON.stringify(data, null, 2));
      setGrantId(null);
      setPhase(1);
    } catch (err: any) {
      setExchangeResult(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleRequestGrant} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Agent Name</label>
            <input
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:border-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Environment</label>
            <select
              value={environment}
              onChange={(e) => setEnvironment(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:border-blue-500 outline-none"
            >
              <option value="development">development</option>
              <option value="staging">staging</option>
              <option value="production">production</option>
              <option value="ci">ci</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Task</label>
            <input
              value={task}
              onChange={(e) => setTask(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:border-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">TTL (seconds)</label>
            <input
              type="number"
              value={ttl}
              onChange={(e) => setTtl(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:border-blue-500 outline-none"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Secret Reference</label>
          <input
            value={secretRef}
            onChange={(e) => setSecretRef(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 font-mono focus:border-blue-500 outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white px-4 py-2 rounded text-sm transition-colors"
        >
          {loading ? "Requesting..." : "Phase 1: Request Grant"}
        </button>
      </form>

      {grantResult && (
        <div>
          <p className="text-xs text-gray-500 mb-1">
            Phase 1 Response (grant token -- no secret):
          </p>
          <pre className="bg-gray-800 border border-gray-700 rounded p-3 text-xs text-gray-300 overflow-x-auto">
            {grantResult}
          </pre>
        </div>
      )}

      {phase === 2 && grantId && (
        <div className="border-t border-gray-700 pt-3">
          <button
            onClick={handleExchange}
            disabled={loading}
            className="bg-amber-600 hover:bg-amber-700 disabled:bg-gray-700 text-white px-4 py-2 rounded text-sm transition-colors"
          >
            {loading ? "Exchanging..." : `Phase 2: Exchange for Secret`}
          </button>
          <p className="text-xs text-gray-500 mt-1">
            Grant ID: {grantId}
          </p>
        </div>
      )}

      {exchangeResult && (
        <div>
          <p className="text-xs text-gray-500 mb-1">
            Phase 2 Response (actual secret):
          </p>
          <pre className="bg-gray-800 border border-amber-700/50 rounded p-3 text-xs text-amber-300 overflow-x-auto">
            {exchangeResult}
          </pre>
        </div>
      )}
    </div>
  );
}
