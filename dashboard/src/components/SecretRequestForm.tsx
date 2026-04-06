"use client";

import { useState } from "react";

export default function SecretRequestForm() {
  const [agentName, setAgentName] = useState("demo-agent-01");
  const [environment, setEnvironment] = useState("development");
  const [task, setTask] = useState("summarize-logs");
  const [secretRef, setSecretRef] = useState(
    "op://demo-vault/api-key/credential"
  );
  const [ttl, setTtl] = useState(300);
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setResult(null);
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
      setResult(JSON.stringify(data, null, 2));
    } catch (err: any) {
      setResult(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
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
        {loading ? "Requesting..." : "Request Secret"}
      </button>
      {result && (
        <pre className="mt-3 bg-gray-800 border border-gray-700 rounded p-3 text-xs text-gray-300 overflow-x-auto">
          {result}
        </pre>
      )}
    </form>
  );
}
