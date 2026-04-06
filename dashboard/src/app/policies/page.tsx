"use client";

import { useEffect, useState } from "react";
import PolicyViewer from "@/components/PolicyViewer";
import type { Policy } from "@/lib/types";
import { fetchJson } from "@/lib/api";

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<Policy[]>([]);

  useEffect(() => {
    fetchJson<Policy[]>("/policies").then(setPolicies).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100 mb-1">Policies</h2>
        <p className="text-sm text-gray-500">
          YAML-based access policies loaded from the policies directory.
          Deny-by-default — if no policy matches, the request is refused.
        </p>
      </div>

      <PolicyViewer policies={policies} />
    </div>
  );
}
