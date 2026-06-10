import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentGate — Credential broker Dashboard",
  description: "Runtime credential broker for AI agents and developer workflows",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="flex">
        <a href="#main-content" className="sr-only focus:not-sr-only">
          Skip to main content
        </a>
        <Sidebar />
        <main id="main-content" className="flex-1 p-6 min-h-screen">
          {children}
        </main>
      </body>
    </html>
  );
}
