"use client";

import { useState } from "react";
import { Button, Field, controlClass } from "@/components/ui";

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
          <Field label="Agent Name">
            {(p) => (
              <input
                {...p}
                value={agentName}
                onChange={(e) => setAgentName(e.target.value)}
                className={controlClass}
              />
            )}
          </Field>
          <Field label="Environment">
            {(p) => (
              <select
                {...p}
                value={environment}
                onChange={(e) => setEnvironment(e.target.value)}
                className={controlClass}
              >
                <option value="development">development</option>
                <option value="staging">staging</option>
                <option value="production">production</option>
                <option value="ci">ci</option>
              </select>
            )}
          </Field>
          <Field label="Task">
            {(p) => (
              <input
                {...p}
                value={task}
                onChange={(e) => setTask(e.target.value)}
                className={controlClass}
              />
            )}
          </Field>
          <Field label="TTL (seconds)">
            {(p) => (
              <input
                {...p}
                type="number"
                value={ttl}
                onChange={(e) => setTtl(Number(e.target.value))}
                className={controlClass}
              />
            )}
          </Field>
        </div>
        <Field label="Secret Reference">
          {(p) => (
            <input
              {...p}
              value={secretRef}
              onChange={(e) => setSecretRef(e.target.value)}
              className={`${controlClass} font-mono`}
            />
          )}
        </Field>
        <Button type="submit" loading={loading}>
          {loading ? "Requesting..." : "Phase 1: Request Grant"}
        </Button>
      </form>

      <div aria-live="polite">
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
      </div>

      {phase === 2 && grantId && (
        <div className="border-t border-gray-700 pt-3">
          <Button variant="warning" onClick={handleExchange} loading={loading}>
            {loading ? "Exchanging..." : `Phase 2: Exchange for Secret`}
          </Button>
          <p className="text-xs text-gray-500 mt-1 font-mono break-all">
            Grant ID: {grantId}
          </p>
        </div>
      )}

      <div aria-live="polite">
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
    </div>
  );
}
