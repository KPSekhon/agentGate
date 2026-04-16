import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";

const C = {
  bg: "#0f0f17",
  card: "#1a1b2e",
  border: "#2a2b3d",
  green: "#9ece6a",
  red: "#f7768e",
  blue: "#7aa2f7",
  purple: "#bb9af7",
  orange: "#ff9e64",
  cyan: "#7dcfff",
  yellow: "#e0af68",
  dim: "#565f89",
  text: "#a9b1d6",
  bright: "#c0caf5",
  sidebar: "#13141f",
};

// Stat card with animated counter
const StatCard: React.FC<{
  label: string;
  value: number;
  color: string;
  delay: number;
  icon: string;
}> = ({ label, value, color, delay, icon }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (frame < delay) return null;

  const scale = spring({
    frame: frame - delay,
    fps,
    from: 0.7,
    to: 1,
    durationInFrames: 15,
  });

  const elapsed = frame - delay;
  const displayValue = Math.min(
    Math.floor(interpolate(elapsed, [0, 25], [0, value], { extrapolateRight: "clamp" })),
    value
  );

  return (
    <div
      style={{
        transform: `scale(${scale})`,
        background: C.card,
        border: `1px solid ${color}30`,
        borderRadius: 16,
        padding: "24px 28px",
        minWidth: 220,
        flex: 1,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 14, color: C.dim, textTransform: "uppercase", letterSpacing: 1 }}>
          {label}
        </span>
        <span style={{ fontSize: 20 }}>{icon}</span>
      </div>
      <div style={{ fontSize: 42, fontWeight: 800, color, marginTop: 8 }}>
        {displayValue}
      </div>
    </div>
  );
};

// Audit log row
const AuditRow: React.FC<{
  action: string;
  agent: string;
  secret: string;
  time: string;
  color: string;
  delay: number;
}> = ({ action, agent, secret, time, color, delay }) => {
  const frame = useCurrentFrame();
  if (frame < delay) return null;

  const opacity = interpolate(frame, [delay, delay + 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const x = interpolate(frame, [delay, delay + 8], [20, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        opacity,
        transform: `translateX(${x}px)`,
        display: "flex",
        alignItems: "center",
        padding: "10px 16px",
        borderBottom: `1px solid ${C.border}`,
        fontSize: 15,
        fontFamily: "monospace",
        gap: 16,
      }}
    >
      <span style={{ color: C.dim, width: 140 }}>{time}</span>
      <span
        style={{
          color: "#000",
          background: color,
          padding: "2px 10px",
          borderRadius: 4,
          fontWeight: 700,
          fontSize: 12,
          width: 100,
          textAlign: "center",
          textTransform: "uppercase",
        }}
      >
        {action}
      </span>
      <span style={{ color: C.bright, width: 220 }}>{agent}</span>
      <span style={{ color: C.dim, flex: 1 }}>{secret}</span>
    </div>
  );
};

// Live feed dot
const LiveDot: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = 0.5 + 0.5 * Math.sin(frame * 0.15);
  return (
    <span
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: C.red,
        opacity,
        marginRight: 8,
      }}
    />
  );
};

// Sidebar nav item
const NavItem: React.FC<{
  label: string;
  active?: boolean;
  icon: string;
}> = ({ label, active, icon }) => (
  <div
    style={{
      padding: "10px 20px",
      display: "flex",
      alignItems: "center",
      gap: 12,
      background: active ? `${C.blue}15` : "transparent",
      borderLeft: active ? `3px solid ${C.blue}` : "3px solid transparent",
      color: active ? C.bright : C.dim,
      fontSize: 14,
      cursor: "pointer",
    }}
  >
    <span style={{ fontSize: 16 }}>{icon}</span>
    {label}
  </div>
);

// --- DASHBOARD OVERVIEW SCENE ---
export const DashboardOverview: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <div
      style={{
        width: 1920,
        height: 1080,
        display: "flex",
        background: C.bg,
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
      }}
    >
      {/* Sidebar */}
      <div
        style={{
          width: 220,
          background: C.sidebar,
          borderRight: `1px solid ${C.border}`,
          display: "flex",
          flexDirection: "column",
          paddingTop: 20,
        }}
      >
        <div
          style={{
            padding: "12px 20px 24px",
            fontSize: 20,
            fontWeight: 800,
            color: C.bright,
            borderBottom: `1px solid ${C.border}`,
            marginBottom: 12,
          }}
        >
          <span
            style={{
              background: `linear-gradient(135deg, ${C.blue}, ${C.purple})`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            AgentGate
          </span>
        </div>
        <NavItem icon="[=]" label="Dashboard" active />
        <NavItem icon="[i]" label="Audit Logs" />
        <NavItem icon="[@]" label="Agents" />
        <NavItem icon="[#]" label="Policies" />
        <NavItem icon="[>]" label="SSH Keys" />
      </div>

      {/* Main content */}
      <div style={{ flex: 1, padding: "32px 40px", overflow: "hidden" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
          <div>
            <div style={{ fontSize: 28, fontWeight: 700, color: C.bright }}>Dashboard</div>
            <div style={{ fontSize: 14, color: C.dim, marginTop: 4 }}>
              Real-time credential broker monitoring
            </div>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              background: C.card,
              padding: "8px 16px",
              borderRadius: 8,
              border: `1px solid ${C.border}`,
            }}
          >
            <LiveDot />
            <span style={{ color: C.text, fontSize: 13 }}>Live</span>
          </div>
        </div>

        {/* Stat cards */}
        <div style={{ display: "flex", gap: 20, marginBottom: 32 }}>
          <StatCard label="Total Requests" value={47} color={C.blue} delay={10} icon="[~]" />
          <StatCard label="Granted" value={38} color={C.green} delay={18} icon="[+]" />
          <StatCard label="Denied" value={6} color={C.red} delay={26} icon="[x]" />
          <StatCard label="Active Grants" value={3} color={C.purple} delay={34} icon="[o]" />
        </div>

        {/* Two-panel layout */}
        <div style={{ display: "flex", gap: 20 }}>
          {/* Recent activity */}
          <div
            style={{
              flex: 2,
              background: C.card,
              borderRadius: 16,
              border: `1px solid ${C.border}`,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                padding: "16px 20px",
                borderBottom: `1px solid ${C.border}`,
                fontSize: 15,
                fontWeight: 600,
                color: C.bright,
              }}
            >
              Recent Audit Trail
            </div>
            <AuditRow action="granted" agent="agent:demo-agent-01" secret="op://demo-vault/api-key/credential" time="12:05:32 UTC" color={C.green} delay={50} />
            <AuditRow action="exchanged" agent="agent:demo-agent-01" secret="op://demo-vault/api-key/credential" time="12:05:34 UTC" color={C.cyan} delay={58} />
            <AuditRow action="denied" agent="agent:demo-agent-01" secret="op://prod-vault/deploy-key/cred" time="12:05:38 UTC" color={C.red} delay={66} />
            <AuditRow action="granted" agent="agent:demo-rogue" secret="op://demo-vault/api-key/credential" time="12:05:41 UTC" color={C.green} delay={74} />
            <AuditRow action="revoked" agent="agent:demo-rogue" secret="op://demo-vault/api-key/credential" time="12:05:45 UTC" color={C.orange} delay={82} />
            <AuditRow action="rate_limited" agent="agent:demo-flood" secret="" time="12:05:49 UTC" color={C.yellow} delay={90} />
            <AuditRow action="granted" agent="agent:ci-deploy" secret="op://ci-vault/npm-token/credential" time="12:05:52 UTC" color={C.green} delay={98} />
          </div>

          {/* Live feed */}
          <div
            style={{
              flex: 1,
              background: C.card,
              borderRadius: 16,
              border: `1px solid ${C.border}`,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                padding: "16px 20px",
                borderBottom: `1px solid ${C.border}`,
                fontSize: 15,
                fontWeight: 600,
                color: C.bright,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <LiveDot /> Live Feed (WebSocket)
            </div>
            {[
              { text: "agent:demo-agent-01 granted api-key", color: C.green, d: 55 },
              { text: "agent:demo-agent-01 exchanged api-key", color: C.cyan, d: 63 },
              { text: "agent:demo-agent-01 denied deploy-key", color: C.red, d: 71 },
              { text: "agent:demo-rogue granted api-key", color: C.green, d: 79 },
              { text: "agent:demo-rogue REVOKED (bulk)", color: C.orange, d: 87 },
              { text: "agent:demo-flood RATE LIMITED", color: C.yellow, d: 95 },
              { text: "anomaly: score 0.7 for demo-flood", color: C.red, d: 103 },
            ].map((item, i) => {
              if (frame < item.d) return null;
              const opacity = interpolate(frame, [item.d, item.d + 6], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              return (
                <div
                  key={i}
                  style={{
                    opacity,
                    padding: "8px 16px",
                    borderBottom: `1px solid ${C.border}`,
                    fontSize: 12,
                    fontFamily: "monospace",
                    color: item.color,
                  }}
                >
                  <span style={{ color: C.dim }}>12:05 </span>
                  {item.text}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

// --- DASHBOARD POLICIES SCENE ---
export const DashboardPolicies: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const policies = [
    {
      name: "default-deny-all",
      priority: 0,
      type: "DENY",
      requester: "*",
      env: "*",
      color: C.red,
    },
    {
      name: "demo-agent-access",
      priority: 10,
      type: "ALLOW",
      requester: "agent:demo-*",
      env: "development, staging",
      color: C.green,
    },
    {
      name: "dev-team-access",
      priority: 10,
      type: "ALLOW",
      requester: "user:*",
      env: "development",
      color: C.green,
    },
    {
      name: "ci-deploy-access",
      priority: 15,
      type: "ALLOW",
      requester: "agent:ci-*",
      env: "staging",
      color: C.green,
    },
    {
      name: "ci-production-deny",
      priority: 100,
      type: "DENY",
      requester: "agent:ci-*",
      env: "production",
      color: C.red,
    },
  ];

  return (
    <div
      style={{
        width: 1920,
        height: 1080,
        display: "flex",
        background: C.bg,
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
      }}
    >
      {/* Sidebar */}
      <div
        style={{
          width: 220,
          background: C.sidebar,
          borderRight: `1px solid ${C.border}`,
          display: "flex",
          flexDirection: "column",
          paddingTop: 20,
        }}
      >
        <div
          style={{
            padding: "12px 20px 24px",
            fontSize: 20,
            fontWeight: 800,
            color: C.bright,
            borderBottom: `1px solid ${C.border}`,
            marginBottom: 12,
          }}
        >
          <span
            style={{
              background: `linear-gradient(135deg, ${C.blue}, ${C.purple})`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            AgentGate
          </span>
        </div>
        <NavItem icon="[=]" label="Dashboard" />
        <NavItem icon="[i]" label="Audit Logs" />
        <NavItem icon="[@]" label="Agents" />
        <NavItem icon="[#]" label="Policies" active />
        <NavItem icon="[>]" label="SSH Keys" />
      </div>

      {/* Main content */}
      <div style={{ flex: 1, padding: "32px 40px" }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: C.bright, marginBottom: 8 }}>
          Policy Engine
        </div>
        <div style={{ fontSize: 14, color: C.dim, marginBottom: 28 }}>
          YAML-based deny-by-default policies. Higher priority wins.
        </div>

        {/* Policy table */}
        <div
          style={{
            background: C.card,
            borderRadius: 16,
            border: `1px solid ${C.border}`,
            overflow: "hidden",
          }}
        >
          {/* Header row */}
          <div
            style={{
              display: "flex",
              padding: "14px 24px",
              borderBottom: `1px solid ${C.border}`,
              fontSize: 12,
              textTransform: "uppercase",
              letterSpacing: 1,
              color: C.dim,
              fontWeight: 600,
            }}
          >
            <span style={{ width: 200 }}>Policy Name</span>
            <span style={{ width: 80 }}>Priority</span>
            <span style={{ width: 80 }}>Type</span>
            <span style={{ width: 220 }}>Requester</span>
            <span style={{ flex: 1 }}>Environment</span>
          </div>

          {policies.map((p, i) => {
            const delay = 15 + i * 12;
            if (frame < delay) return null;
            const opacity = interpolate(frame, [delay, delay + 8], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            return (
              <div
                key={i}
                style={{
                  opacity,
                  display: "flex",
                  padding: "14px 24px",
                  borderBottom: `1px solid ${C.border}`,
                  fontSize: 15,
                  alignItems: "center",
                }}
              >
                <span style={{ width: 200, color: C.bright, fontWeight: 600 }}>
                  {p.name}
                </span>
                <span style={{ width: 80, color: C.yellow, fontWeight: 700 }}>
                  {p.priority}
                </span>
                <span
                  style={{
                    width: 80,
                  }}
                >
                  <span
                    style={{
                      background: p.color,
                      color: "#000",
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontWeight: 700,
                      fontSize: 11,
                    }}
                  >
                    {p.type}
                  </span>
                </span>
                <span style={{ width: 220, color: C.purple, fontFamily: "monospace", fontSize: 14 }}>
                  {p.requester}
                </span>
                <span style={{ flex: 1, color: C.text, fontFamily: "monospace", fontSize: 14 }}>
                  {p.env}
                </span>
              </div>
            );
          })}
        </div>

        {/* YAML preview */}
        {frame >= 90 && (
          <div
            style={{
              marginTop: 24,
              opacity: interpolate(frame, [90, 100], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            <div
              style={{
                background: C.card,
                borderRadius: 16,
                border: `1px solid ${C.border}`,
                padding: "20px 28px",
                fontFamily: "monospace",
                fontSize: 15,
                lineHeight: 1.7,
              }}
            >
              <div style={{ color: C.dim, marginBottom: 12, fontSize: 12, textTransform: "uppercase", letterSpacing: 1 }}>
                policies/demo-agent.yaml
              </div>
              <div>
                <span style={{ color: C.red }}>name</span>
                <span style={{ color: C.text }}>: </span>
                <span style={{ color: C.green }}>demo-agent-access</span>
              </div>
              <div>
                <span style={{ color: C.red }}>priority</span>
                <span style={{ color: C.text }}>: </span>
                <span style={{ color: C.orange }}>10</span>
              </div>
              <div>
                <span style={{ color: C.red }}>conditions</span>
                <span style={{ color: C.text }}>:</span>
              </div>
              <div>
                <span style={{ color: C.text }}>{"  "}</span>
                <span style={{ color: C.red }}>requester</span>
                <span style={{ color: C.text }}>: </span>
                <span style={{ color: C.green }}>"agent:demo-*"</span>
              </div>
              <div>
                <span style={{ color: C.text }}>{"  "}</span>
                <span style={{ color: C.red }}>environment</span>
                <span style={{ color: C.text }}>: </span>
                <span style={{ color: C.green }}>[development, staging]</span>
              </div>
              <div>
                <span style={{ color: C.red }}>grants</span>
                <span style={{ color: C.text }}>:</span>
              </div>
              <div>
                <span style={{ color: C.text }}>{"  "}- </span>
                <span style={{ color: C.red }}>secret_ref</span>
                <span style={{ color: C.text }}>: </span>
                <span style={{ color: C.green }}>"op://demo-vault/*"</span>
              </div>
              <div>
                <span style={{ color: C.text }}>{"    "}</span>
                <span style={{ color: C.red }}>ttl_seconds</span>
                <span style={{ color: C.text }}>: </span>
                <span style={{ color: C.orange }}>300</span>
              </div>
              <div>
                <span style={{ color: C.text }}>{"    "}</span>
                <span style={{ color: C.red }}>max_uses</span>
                <span style={{ color: C.text }}>: </span>
                <span style={{ color: C.orange }}>1</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
