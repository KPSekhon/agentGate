import React from "react";
import { AbsoluteFill, Still } from "remotion";

const C = {
  bg: "#0f0f17",
  blue: "#7aa2f7",
  purple: "#bb9af7",
  red: "#f7768e",
  green: "#9ece6a",
  cyan: "#7dcfff",
  dim: "#565f89",
  bright: "#c0caf5",
};

export const Thumbnail: React.FC = () => {
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 30% 50%, #1e2040 0%, ${C.bg} 65%)`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
        padding: 80,
      }}
    >
      {/* Decorative code lines in background */}
      <div
        style={{
          position: "absolute",
          top: 60,
          right: 80,
          opacity: 0.12,
          fontFamily: "monospace",
          fontSize: 18,
          lineHeight: 2,
          color: C.blue,
          textAlign: "right",
        }}
      >
        {`POST /agent/request-secret
{ "agent": "demo-agent-01" }
{ "grant_id": "a1b2c3d4..." }
{ "uses_remaining": 1 }
{ "secret_value": "<< NOT HERE >>" }

POST /agent/exchange
{ "secret_value": "sk-live-..." }
{ "uses_remaining": 0 }

HTTP 410 GONE`}
      </div>

      {/* Decorative policy block bottom-left */}
      <div
        style={{
          position: "absolute",
          bottom: 60,
          left: 80,
          opacity: 0.1,
          fontFamily: "monospace",
          fontSize: 16,
          lineHeight: 2,
          color: C.purple,
        }}
      >
        {`name: default-deny-all
priority: 0
deny: true
conditions:
  requester: "*"
  environment: "*"`}
      </div>

      {/* Main content */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", maxWidth: 1200, zIndex: 1 }}>
        {/* Top label */}
        <div
          style={{
            display: "flex",
            gap: 12,
            marginBottom: 24,
          }}
        >
          <span
            style={{
              background: C.red,
              color: "#000",
              padding: "6px 16px",
              borderRadius: 6,
              fontWeight: 800,
              fontSize: 18,
              textTransform: "uppercase",
              letterSpacing: 1,
            }}
          >
            .env is not security
          </span>
          <span
            style={{
              background: C.green,
              color: "#000",
              padding: "6px 16px",
              borderRadius: 6,
              fontWeight: 800,
              fontSize: 18,
              textTransform: "uppercase",
              letterSpacing: 1,
            }}
          >
            this is
          </span>
        </div>

        {/* Title */}
        <div
          style={{
            fontSize: 82,
            fontWeight: 900,
            color: "#fff",
            lineHeight: 1.1,
            marginBottom: 20,
            letterSpacing: -2,
          }}
        >
          i built a secret
          <br />
          broker for
          <br />
          <span
            style={{
              background: `linear-gradient(135deg, ${C.blue}, ${C.purple})`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            ai agents
          </span>
        </div>

        {/* Subtitle tags */}
        <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
          {["two-phase grants", "deny-by-default", "rate limiting", "audit trail"].map(
            (tag, i) => (
              <span
                key={i}
                style={{
                  background: "rgba(42,43,61,0.8)",
                  border: `1px solid ${C.dim}`,
                  borderRadius: 8,
                  padding: "8px 18px",
                  color: C.bright,
                  fontSize: 17,
                  fontFamily: "monospace",
                  fontWeight: 600,
                }}
              >
                {tag}
              </span>
            )
          )}
        </div>
      </div>

      {/* Terminal mockup on the right */}
      <div
        style={{
          position: "absolute",
          right: 80,
          bottom: 120,
          width: 480,
          background: "#1a1b26",
          borderRadius: 12,
          border: `1px solid #2a2b3d`,
          overflow: "hidden",
          boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
        }}
      >
        {/* Terminal title bar */}
        <div
          style={{
            background: "#16161e",
            padding: "8px 14px",
            display: "flex",
            alignItems: "center",
            gap: 6,
            borderBottom: "1px solid #2a2b3d",
          }}
        >
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#ff5f57" }} />
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#febc2e" }} />
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#28c840" }} />
        </div>
        <div
          style={{
            padding: "16px 18px",
            fontFamily: "monospace",
            fontSize: 14,
            lineHeight: 1.7,
            color: C.bright,
          }}
        >
          <div>
            <span style={{ color: C.dim }}>$ </span>
            <span style={{ color: C.cyan }}>POST /agent/exchange</span>
          </div>
          <div style={{ marginTop: 8 }}>
            <span style={{ color: C.green, fontWeight: 700 }}>SECRET DELIVERED</span>
          </div>
          <div>
            <span style={{ color: C.dim }}>value: </span>
            <span style={{ color: C.green }}>sk-live-...x9f2</span>
          </div>
          <div>
            <span style={{ color: C.dim }}>uses:  </span>
            <span style={{ color: C.red, fontWeight: 700 }}>0</span>
            <span style={{ color: C.dim }}> (spent)</span>
          </div>
          <div style={{ marginTop: 10 }}>
            <span style={{ color: C.dim }}>$ </span>
            <span style={{ color: C.cyan }}>POST /agent/exchange</span>
          </div>
          <div>
            <span style={{ color: C.red, fontWeight: 700 }}>HTTP 410 GONE</span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
