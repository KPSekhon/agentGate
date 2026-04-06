"use client";

import { useEffect, useState } from "react";
import StatCard from "@/components/StatCard";
import LiveFeed from "@/components/LiveFeed";
import SecretRequestForm from "@/components/SecretRequestForm";
import type { AuditStats } from "@/lib/types";
import { fetchJson } from "@/lib/api";

export default function DashboardHome() {
  const [stats, setStats] = useState<AuditStats | null>(null);

  useEffect(() => {
    const load = () =>
      fetchJson<AuditStats>("/audit/stats").then(setStats).catch(() => {});
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100 mb-1">Dashboard</h2>
        <p className="text-sm text-gray-500">
          Real-time overview of credential access across agents and workflows
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="Requests Today"
          value={stats?.total_requests_today ?? "—"}
          color="blue"
        />
        <StatCard
          title="Denied"
          value={stats?.denied_requests_today ?? "—"}
          color="red"
        />
        <StatCard
          title="Active Grants"
          value={stats?.active_grants ?? "—"}
          color="green"
        />
        <StatCard
          title="Anomaly Alerts"
          value={stats?.anomaly_alerts_today ?? "—"}
          color="amber"
        />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm font-medium text-gray-400 mb-3">
            Test Secret Request
          </h3>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <SecretRequestForm />
          </div>
        </div>
        <div>
          <h3 className="text-sm font-medium text-gray-400 mb-3">
            Live Activity
          </h3>
          <LiveFeed />
        </div>
      </div>
    </div>
  );
}
