import React from "react";

export const Terminal: React.FC<{
  children: React.ReactNode;
  title?: string;
}> = ({ children, title = "Terminal" }) => {
  return (
    <div
      style={{
        background: "#1a1b26",
        borderRadius: 16,
        overflow: "hidden",
        width: 1720,
        margin: "0 auto",
        boxShadow: "0 25px 80px rgba(0,0,0,0.6)",
        border: "1px solid #2a2b3d",
      }}
    >
      {/* Title bar */}
      <div
        style={{
          background: "#16161e",
          padding: "12px 20px",
          display: "flex",
          alignItems: "center",
          gap: 10,
          borderBottom: "1px solid #2a2b3d",
        }}
      >
        <div style={{ display: "flex", gap: 8 }}>
          <div
            style={{
              width: 14,
              height: 14,
              borderRadius: "50%",
              background: "#ff5f57",
            }}
          />
          <div
            style={{
              width: 14,
              height: 14,
              borderRadius: "50%",
              background: "#febc2e",
            }}
          />
          <div
            style={{
              width: 14,
              height: 14,
              borderRadius: "50%",
              background: "#28c840",
            }}
          />
        </div>
        <span
          style={{
            color: "#565f89",
            fontSize: 14,
            fontFamily: "monospace",
            marginLeft: 12,
          }}
        >
          {title}
        </span>
      </div>

      {/* Content */}
      <div
        style={{
          padding: "24px 28px",
          fontFamily: "'JetBrains Mono', 'Cascadia Code', 'Fira Code', monospace",
          fontSize: 18,
          lineHeight: 1.6,
          color: "#a9b1d6",
          minHeight: 700,
          whiteSpace: "pre-wrap",
        }}
      >
        {children}
      </div>
    </div>
  );
};
