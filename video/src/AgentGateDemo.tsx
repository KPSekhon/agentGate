import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
  AbsoluteFill,
  Audio,
  staticFile,
} from "remotion";
import { Terminal } from "./Terminal";
import { DashboardOverview, DashboardPolicies } from "./Dashboard";

// Import audio files directly via webpack instead of staticFile
// (staticFile + public dir fails on Windows/OneDrive paths)
const voiceoverUrl = new URL("../public/voiceover.mp3", import.meta.url).href;
const musicUrl = new URL("../public/music.mp3", import.meta.url).href;

// ============================================================
// Voice-synced timing (75s voiceover)
//
// intro       :  0.0s -  4.8s  (frames    0 -  143)
// problem     :  4.8s - 18.2s  (frames  143 -  545)
// phase1      : 18.2s - 31.6s  (frames  545 -  947)
// phase2      : 31.6s - 40.1s  (frames  947 - 1201)
// deny        : 40.1s - 47.3s  (frames 1201 - 1418)
// dashboard   : 47.3s - 55.8s  (frames 1418 - 1672)
// policies    : 55.8s - 65.9s  (frames 1672 - 1976)
// outro       : 65.9s - 74.8s  (frames 1976 - 2242)
// ============================================================

const C = {
  bg: "#0f0f17",
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
};

// --- Shared components ---

const Typewriter: React.FC<{
  text: string;
  startFrame: number;
  charsPerFrame?: number;
  color?: string;
}> = ({ text, startFrame, charsPerFrame = 2, color = C.text }) => {
  const frame = useCurrentFrame();
  const elapsed = frame - startFrame;
  if (elapsed < 0) return null;
  const chars = Math.min(Math.floor(elapsed * charsPerFrame), text.length);
  return (
    <span style={{ color }}>
      {text.slice(0, chars)}
      {chars < text.length && (
        <span style={{ opacity: Math.sin(frame * 0.3) > 0 ? 1 : 0, color: C.green }}>_</span>
      )}
    </span>
  );
};

const FadeIn: React.FC<{
  children: React.ReactNode;
  startFrame: number;
  duration?: number;
}> = ({ children, startFrame, duration = 10 }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [startFrame, startFrame + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const y = interpolate(frame, [startFrame, startFrame + duration], [12, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  if (frame < startFrame) return null;
  return <div style={{ opacity, transform: `translateY(${y}px)` }}>{children}</div>;
};

const SectionHeader: React.FC<{
  text: string;
  startFrame: number;
  color?: string;
}> = ({ text, startFrame, color = C.blue }) => {
  const frame = useCurrentFrame();
  if (frame < startFrame) return null;
  const width = interpolate(frame, [startFrame, startFrame + 15], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div style={{ marginTop: 8, marginBottom: 8 }}>
      <div style={{ height: 2, background: color, width: `${width}%`, marginBottom: 6, opacity: 0.6 }} />
      <span style={{ color, fontSize: 20, fontWeight: 700 }}>{text}</span>
    </div>
  );
};

// Cross-fade wrapper
const CrossFade: React.FC<{ children: React.ReactNode; fadeDuration?: number }> = ({
  children,
  fadeDuration = 12,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const fadeIn = interpolate(frame, [0, fadeDuration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - fadeDuration, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  return <AbsoluteFill style={{ opacity: Math.min(fadeIn, fadeOut) }}>{children}</AbsoluteFill>;
};

// Caption bar at bottom
const Caption: React.FC<{
  text: string;
  startFrame: number;
  duration: number;
}> = ({ text, startFrame, duration }) => {
  const frame = useCurrentFrame();
  if (frame < startFrame || frame > startFrame + duration) return null;
  const opacity = interpolate(
    frame,
    [startFrame, startFrame + 8, startFrame + duration - 8, startFrame + duration],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  return (
    <div
      style={{
        position: "absolute",
        bottom: 60,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity,
      }}
    >
      <div
        style={{
          background: "rgba(0,0,0,0.75)",
          backdropFilter: "blur(8px)",
          padding: "14px 36px",
          borderRadius: 12,
          maxWidth: 1400,
          textAlign: "center",
          fontSize: 22,
          color: "#e0e0e0",
          fontFamily: "'Inter', 'Segoe UI', sans-serif",
          lineHeight: 1.5,
        }}
      >
        {text}
      </div>
    </div>
  );
};

// ============================================================
// SCENES
// ============================================================

// --- INTRO (0-4.8s / frames 0-143) ---
const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const titleScale = spring({ frame, fps, from: 0.8, to: 1, durationInFrames: 25 });
  const titleOp = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });
  const subOp = interpolate(frame, [30, 50], [0, 1], { extrapolateRight: "clamp" });

  return (
    <CrossFade>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at center, #1a1b3a 0%, ${C.bg} 70%)`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div style={{ opacity: titleOp, transform: `scale(${titleScale})`, textAlign: "center" }}>
          <div
            style={{
              fontSize: 100,
              fontWeight: 800,
              fontFamily: "'Inter', 'Segoe UI', sans-serif",
              background: `linear-gradient(135deg, ${C.blue}, ${C.purple})`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              letterSpacing: -3,
            }}
          >
            AgentGate
          </div>
        </div>
        <div
          style={{
            opacity: subOp,
            fontSize: 30,
            color: C.dim,
            fontFamily: "monospace",
            marginTop: 24,
          }}
        >
          runtime credential broker for ai agents
        </div>
      </AbsoluteFill>
      <Caption text="AgentGate. A runtime credential broker for AI agents." startFrame={0} duration={140} />
    </CrossFade>
  );
};

// --- PROBLEM (4.8-18.2s / frames 143-545) ---
const ProblemScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const problems = [
    "AI agents need API keys, database creds, deploy tokens",
    "Secrets sit in .env files with no expiry or scope",
    "No audit trail when an agent accesses a secret",
    "One compromised agent = everything leaks",
  ];

  return (
    <CrossFade>
      <AbsoluteFill
        style={{
          background: C.bg,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: 100,
        }}
      >
        <FadeIn startFrame={0} duration={12}>
          <div
            style={{
              fontSize: 48,
              fontWeight: 700,
              color: C.red,
              fontFamily: "'Inter', 'Segoe UI', sans-serif",
              marginBottom: 48,
            }}
          >
            the problem
          </div>
        </FadeIn>

        {problems.map((p, i) => {
          const delay = 20 + i * 25;
          if (frame < delay) return null;
          const s = spring({ frame: frame - delay, fps, from: 0.9, to: 1, durationInFrames: 12 });
          const op = interpolate(frame, [delay, delay + 10], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <div
              key={i}
              style={{
                opacity: op,
                transform: `scale(${s})`,
                fontSize: 26,
                color: C.text,
                fontFamily: "'Inter', 'Segoe UI', sans-serif",
                marginBottom: 22,
                display: "flex",
                alignItems: "center",
                gap: 16,
              }}
            >
              <span style={{ color: C.red, fontSize: 28, fontWeight: 700, width: 30, textAlign: "center" }}>x</span>
              {p}
            </div>
          );
        })}
      </AbsoluteFill>
    </CrossFade>
  );
};

// --- PHASE 1 (18.2-31.6s / frames 545-947, local 0-402) ---
const Phase1Scene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <CrossFade>
      <AbsoluteFill style={{ background: C.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Terminal title="phase 1: request a grant (no secret returned)">
          <FadeIn startFrame={0}>
            <span style={{ color: C.dim }}>$ </span>
            <Typewriter text="POST /agent/request-secret" startFrame={5} color={C.cyan} />
          </FadeIn>

          <FadeIn startFrame={20} duration={8}>
            <div style={{ marginTop: 12, color: C.dim }}>
              {"  "}agent: <span style={{ color: C.bright }}>demo-agent-01</span>
            </div>
            <div style={{ color: C.dim }}>
              {"  "}env:{"   "}<span style={{ color: C.green }}>development</span>
            </div>
            <div style={{ color: C.dim }}>
              {"  "}task:{"  "}<span style={{ color: C.bright }}>summarize-logs</span>
            </div>
            <div style={{ color: C.dim }}>
              {"  "}ref:{"   "}<span style={{ color: C.orange }}>op://demo-vault/api-key/credential</span>
            </div>
          </FadeIn>

          <FadeIn startFrame={50} duration={8}>
            <div style={{ marginTop: 20 }}>
              <span style={{ background: C.green, color: "#000", padding: "2px 10px", borderRadius: 4, fontWeight: 700, fontSize: 16 }}>
                GRANTED
              </span>
              <span style={{ color: C.dim, marginLeft: 12 }}>-- but NO secret in the response</span>
            </div>
          </FadeIn>

          <FadeIn startFrame={70} duration={10}>
            <div style={{ marginTop: 16, marginLeft: 16 }}>
              <div><span style={{ color: C.dim }}>grant_id:{"       "}</span><span style={{ color: C.purple }}>a1b2c3d4-e5f6-7890-abcd-ef1234567890</span></div>
              <div><span style={{ color: C.dim }}>ttl_seconds:{"    "}</span><span style={{ color: C.yellow }}>300</span></div>
              <div><span style={{ color: C.dim }}>uses_remaining:{"  "}</span><span style={{ color: C.yellow }}>1</span></div>
              <div><span style={{ color: C.dim }}>policy:{"         "}</span><span style={{ color: C.cyan }}>demo-agent-access</span></div>
              <div style={{ marginTop: 10 }}>
                <span style={{ color: C.dim }}>secret_value:{"   "}</span>
                <span style={{ color: C.red, fontWeight: 700, fontSize: 22 }}>{"<< NOT HERE >>"}</span>
              </div>
            </div>
          </FadeIn>

          {frame >= 110 && (
            <FadeIn startFrame={110} duration={10}>
              <div style={{ marginTop: 20, padding: "12px 20px", background: "rgba(122,162,247,0.1)", borderLeft: `3px solid ${C.blue}`, borderRadius: 4, color: C.blue, fontSize: 16 }}>
                just a token with a TTL and use limit. not the secret.
              </div>
            </FadeIn>
          )}
        </Terminal>
      </AbsoluteFill>
    </CrossFade>
  );
};

// --- PHASE 2 + EXHAUSTED (31.6-40.1s / frames 947-1201, local 0-254) ---
const Phase2Scene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <CrossFade>
      <AbsoluteFill style={{ background: C.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Terminal title="phase 2: exchange grant for the actual secret">
          <FadeIn startFrame={0}>
            <span style={{ color: C.dim }}>$ </span>
            <Typewriter text="POST /agent/exchange" startFrame={5} color={C.cyan} />
          </FadeIn>

          <FadeIn startFrame={18} duration={8}>
            <div style={{ marginTop: 12, color: C.dim }}>
              {"  "}grant_id: <span style={{ color: C.purple }}>a1b2c3d4-e5f6-7890-abcd-ef1234567890</span>
            </div>
          </FadeIn>

          <FadeIn startFrame={35} duration={8}>
            <div style={{ marginTop: 20 }}>
              <span style={{ background: C.green, color: "#000", padding: "2px 10px", borderRadius: 4, fontWeight: 700, fontSize: 16 }}>
                SECRET DELIVERED
              </span>
            </div>
            <div style={{ marginTop: 12, marginLeft: 16 }}>
              <div><span style={{ color: C.dim }}>secret_value:{"   "}</span><span style={{ color: C.green, fontWeight: 700 }}>demo-api-k...cbd1</span></div>
              <div><span style={{ color: C.dim }}>uses_remaining:{"  "}</span><span style={{ color: C.red, fontWeight: 700 }}>0</span><span style={{ color: C.dim }}> (grant is now spent)</span></div>
            </div>
          </FadeIn>

          <FadeIn startFrame={75} duration={8}>
            <div style={{ marginTop: 28 }}>
              <span style={{ color: C.dim }}>$ </span>
              <span style={{ color: C.cyan }}>POST /agent/exchange (same grant_id)</span>
            </div>
          </FadeIn>

          <FadeIn startFrame={95} duration={8}>
            <div style={{ marginTop: 12 }}>
              <span style={{ background: C.red, color: "#000", padding: "2px 10px", borderRadius: 4, fontWeight: 700, fontSize: 16 }}>
                HTTP 410 GONE
              </span>
              <span style={{ color: C.red, marginLeft: 12 }}>this grant has been revoked.</span>
            </div>
            <div style={{ marginTop: 12, padding: "12px 20px", background: "rgba(247,118,142,0.1)", borderLeft: `3px solid ${C.red}`, borderRadius: 4, color: C.red, fontSize: 16 }}>
              one use. the secret is gone forever.
            </div>
          </FadeIn>
        </Terminal>
      </AbsoluteFill>
    </CrossFade>
  );
};

// --- DENY (40.1-47.3s / frames 1201-1418, local 0-217) ---
const DenyScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <CrossFade>
      <AbsoluteFill style={{ background: C.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Terminal title="policy enforcement: deny by default">
          <FadeIn startFrame={0}>
            <span style={{ color: C.dim }}>$ </span>
            <Typewriter text="POST /agent/request-secret" startFrame={5} color={C.cyan} />
          </FadeIn>

          <FadeIn startFrame={20} duration={8}>
            <div style={{ marginTop: 12, color: C.dim }}>
              {"  "}agent: <span style={{ color: C.bright }}>demo-agent-01</span>
            </div>
            <div style={{ color: C.dim }}>
              {"  "}env:{"   "}<span style={{ color: C.red, fontWeight: 700 }}>production</span>
            </div>
            <div style={{ color: C.dim }}>
              {"  "}ref:{"   "}<span style={{ color: C.orange }}>op://prod-vault/deploy-key/credential</span>
            </div>
          </FadeIn>

          <FadeIn startFrame={45} duration={8}>
            <div style={{ marginTop: 20 }}>
              <span style={{ background: C.red, color: "#000", padding: "2px 10px", borderRadius: 4, fontWeight: 700, fontSize: 16 }}>
                HTTP 403 DENIED
              </span>
            </div>
            <div style={{ marginTop: 12, marginLeft: 16, color: C.red }}>
              denied by policy 'default-deny-all'
              <br />no matching policy, no access.
            </div>
          </FadeIn>

          <FadeIn startFrame={80} duration={10}>
            <div style={{ marginTop: 20, padding: "12px 20px", background: "rgba(122,162,247,0.1)", borderLeft: `3px solid ${C.blue}`, borderRadius: 4, color: C.blue, fontSize: 16 }}>
              deny by default. if there's no policy that allows it, it doesn't happen.
            </div>
          </FadeIn>
        </Terminal>
      </AbsoluteFill>
    </CrossFade>
  );
};

// --- DASHBOARD (47.3-55.8s / frames 1418-1672, local 0-254) ---
// Uses DashboardOverview from Dashboard.tsx

// --- REVOKE + RATE LIMIT (55.8-65.9s / frames 1672-1976, local 0-304) ---
const RevokeScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <CrossFade>
      <AbsoluteFill style={{ background: C.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Terminal title="incident response: revoke + rate limit">
          <SectionHeader text="BULK REVOCATION" startFrame={0} color={C.orange} />

          <FadeIn startFrame={8} duration={8}>
            <div style={{ marginTop: 8, color: C.dim }}>3 active grants for 'demo-rogue'</div>
          </FadeIn>

          <FadeIn startFrame={20}>
            <div style={{ marginTop: 8 }}>
              <span style={{ color: C.dim }}>$ </span>
              <Typewriter text="POST /agent/revoke-agent" startFrame={23} color={C.cyan} />
            </div>
          </FadeIn>

          <FadeIn startFrame={42} duration={8}>
            <div style={{ marginTop: 12 }}>
              <span style={{ background: C.orange, color: "#000", padding: "2px 10px", borderRadius: 4, fontWeight: 700, fontSize: 16 }}>REVOKED</span>
              <span style={{ color: C.orange, marginLeft: 12, fontWeight: 700 }}>3 grants killed instantly</span>
            </div>
            <div style={{ marginTop: 8, color: C.dim, fontSize: 16 }}>one api call. all active grants for the agent are gone.</div>
          </FadeIn>

          <SectionHeader text="RATE LIMITING" startFrame={80} color={C.yellow} />

          <FadeIn startFrame={90} duration={8}>
            <div style={{ marginTop: 8, color: C.dim }}>12 rapid requests from agent:demo-flood...</div>
          </FadeIn>

          {frame >= 105 && (
            <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 6 }}>
              {Array.from({ length: 12 }).map((_, i) => {
                const showFrame = 105 + i * 4;
                if (frame < showFrame) return null;
                const isBlocked = i >= 7;
                const opacity = interpolate(frame, [showFrame, showFrame + 4], [0, 1], { extrapolateRight: "clamp" });
                return (
                  <span
                    key={i}
                    style={{
                      opacity,
                      display: "inline-block",
                      padding: "4px 12px",
                      borderRadius: 4,
                      fontSize: 14,
                      fontWeight: 700,
                      background: isBlocked ? "rgba(247,118,142,0.2)" : "rgba(158,206,106,0.2)",
                      color: isBlocked ? C.red : C.green,
                      border: `1px solid ${isBlocked ? C.red : C.green}`,
                    }}
                  >
                    {i + 1} {isBlocked ? "BLOCKED" : "OK"}
                  </span>
                );
              })}
            </div>
          )}

          <FadeIn startFrame={160} duration={10}>
            <div style={{ marginTop: 16, padding: "12px 20px", background: "rgba(224,175,104,0.1)", borderLeft: `3px solid ${C.yellow}`, borderRadius: 4, color: C.yellow, fontSize: 16 }}>
              10 requests/minute per agent. after that, 429.
            </div>
          </FadeIn>
        </Terminal>
      </AbsoluteFill>
    </CrossFade>
  );
};

// --- OUTRO (65.9-74.8s / frames 1976-2242, local 0-266) ---
const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({ frame, fps, from: 0.9, to: 1, durationInFrames: 20 });
  const opacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });

  const features = [
    "two-phase grants",
    "deny-by-default policies",
    "per-agent rate limiting",
    "bulk revocation",
    "real-time audit dashboard",
    "1password sdk",
  ];

  return (
    <CrossFade fadeDuration={15}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at center, #1a1b3a 0%, ${C.bg} 70%)`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          opacity,
          transform: `scale(${scale})`,
        }}
      >
        <div
          style={{
            fontSize: 80,
            fontWeight: 800,
            fontFamily: "'Inter', 'Segoe UI', sans-serif",
            background: `linear-gradient(135deg, ${C.blue}, ${C.purple})`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          AgentGate
        </div>

        <div style={{ marginTop: 36, display: "flex", flexWrap: "wrap", gap: 12, justifyContent: "center", maxWidth: 1000 }}>
          {features.map((f, i) => {
            const showFrame = 20 + i * 10;
            if (frame < showFrame) return null;
            const s = spring({ frame: frame - showFrame, fps, from: 0.8, to: 1, durationInFrames: 12 });
            return (
              <div
                key={i}
                style={{
                  transform: `scale(${s})`,
                  background: "rgba(42,43,61,0.6)",
                  border: `1px solid ${C.purple}40`,
                  borderRadius: 10,
                  padding: "12px 24px",
                  color: C.bright,
                  fontSize: 18,
                  fontFamily: "monospace",
                }}
              >
                {f}
              </div>
            );
          })}
        </div>

        <FadeIn startFrame={100} duration={15}>
          <div style={{ marginTop: 44, fontSize: 24, color: C.text, fontFamily: "'Inter', 'Segoe UI', sans-serif", fontWeight: 300 }}>
            stop giving ai agents your .env file
          </div>
        </FadeIn>
      </AbsoluteFill>
    </CrossFade>
  );
};

// ============================================================
// MAIN COMPOSITION - synced to 75s voiceover
// ============================================================
export const AgentGateDemo: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      {/* Voiceover */}
      <Audio src={voiceoverUrl} volume={1} />

      {/* Background music (quiet, under the voice) */}
      <Audio src={musicUrl} volume={0.08} />

      {/* Intro: 0-4.8s (frames 0-143) */}
      <Sequence from={0} durationInFrames={155}>
        <IntroScene />
      </Sequence>

      {/* Problem: 4.8-18.2s (frames 143-545) */}
      <Sequence from={140} durationInFrames={415}>
        <ProblemScene />
      </Sequence>

      {/* Phase 1: 18.2-31.6s (frames 545-947) */}
      <Sequence from={545} durationInFrames={410}>
        <Phase1Scene />
      </Sequence>

      {/* Phase 2 + Exhausted: 31.6-40.1s (frames 947-1201) */}
      <Sequence from={940} durationInFrames={270}>
        <Phase2Scene />
      </Sequence>

      {/* Deny: 40.1-47.3s (frames 1201-1418) */}
      <Sequence from={1200} durationInFrames={225}>
        <DenyScene />
      </Sequence>

      {/* Dashboard: 47.3-55.8s (frames 1418-1672) */}
      <Sequence from={1415} durationInFrames={265}>
        <CrossFade>
          <DashboardOverview />
        </CrossFade>
      </Sequence>

      {/* Revoke + Rate Limit: 55.8-65.9s (frames 1672-1976) */}
      <Sequence from={1670} durationInFrames={315}>
        <RevokeScene />
      </Sequence>

      {/* Outro: 65.9-74.8s (frames 1976-2242) */}
      <Sequence from={1970} durationInFrames={280}>
        <OutroScene />
      </Sequence>
    </AbsoluteFill>
  );
};
