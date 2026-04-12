export interface AuditLog {
  id: string;
  timestamp: string;
  requester: string;
  environment: string;
  task: string;
  secret_ref: string;
  action: "granted" | "denied" | "released" | "expired" | "exchanged" | "revoked" | "rate_limited";
  policy_name: string;
  ttl_seconds: number;
  anomaly_score: number;
}

export interface AuditStats {
  total_requests_today: number;
  denied_requests_today: number;
  active_grants: number;
  anomaly_alerts_today: number;
}

export interface GrantResponse {
  grant_id: string;
  expires_at: string;
  ttl_seconds: number;
  uses_remaining: number;
  policy: string;
}

export interface SecretResponse {
  grant_id: string;
  secret_value: string;
  uses_remaining: number;
}

export interface Policy {
  name: string;
  description: string;
  priority: number;
  deny: boolean;
  conditions: { requester: string; environment: string; task: string }[];
  grants: { secret_ref: string; ttl_seconds: number; max_uses: number }[];
}

export interface SSHKey {
  id: string;
  name: string;
  fingerprint: string;
  key_type: string;
  has_passphrase: boolean;
  description: string;
  created_at: string;
  last_used_at: string | null;
  last_used_by: string;
  access_count: number;
}
