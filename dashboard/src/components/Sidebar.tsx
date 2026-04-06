"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/audit", label: "Audit Logs" },
  { href: "/agents", label: "Agent Sessions" },
  { href: "/policies", label: "Policies" },
  { href: "/ssh", label: "SSH Keys" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 min-h-screen p-4 flex flex-col gap-1">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-blue-400 tracking-tight">
          AgentGate
        </h1>
        <p className="text-xs text-gray-500 mt-0.5">Credential Broker</p>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.map(({ href, label }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`px-3 py-2 rounded text-sm transition-colors ${
                active
                  ? "bg-blue-600/20 text-blue-300 font-medium"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
              }`}
            >
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto pt-4 border-t border-gray-800 text-xs text-gray-600">
        v0.1.0 — Demo Mode
      </div>
    </aside>
  );
}
