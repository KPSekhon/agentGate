"use client";

import { useId } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

/**
 * Small set of reusable, accessible UI primitives shared across the dashboard.
 * Centralizing them keeps focus states, labels, and ARIA wiring consistent
 * instead of being re-implemented (often incorrectly) on every page.
 */

/** Shared input/select styling, including a visible keyboard-focus ring. */
export const controlClass =
  "w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:border-blue-400";

type ButtonVariant = "primary" | "warning";

const buttonVariants: Record<ButtonVariant, string> = {
  primary: "bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white focus-visible:ring-blue-400",
  warning: "bg-amber-600 hover:bg-amber-700 disabled:bg-gray-700 text-white focus-visible:ring-amber-400",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
}

/** Button with consistent focus-visible ring and a `loading` state that
 *  disables the control and exposes `aria-busy` to assistive tech. */
export function Button({
  variant = "primary",
  loading = false,
  disabled,
  className = "",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={
        "px-4 py-2 rounded text-sm font-medium transition-colors disabled:cursor-not-allowed " +
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-950 " +
        `${buttonVariants[variant]} ${className}`
      }
    >
      {children}
    </button>
  );
}

interface FieldProps {
  label: string;
  hint?: string;
  /** Render-prop receives the id + aria wiring to spread onto the control,
   *  so the <label> and any hint text are always correctly associated. */
  children: (props: { id: string; "aria-describedby"?: string }) => ReactNode;
}

export function Field({ label, hint, children }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div>
      <label htmlFor={id} className="block text-xs text-gray-500 mb-1">
        {label}
      </label>
      {children({ id, "aria-describedby": hintId })}
      {hint && (
        <p id={hintId} className="text-xs text-gray-600 mt-1">
          {hint}
        </p>
      )}
    </div>
  );
}

type BadgeTone = "gray" | "blue" | "green" | "red" | "amber";

const badgeTones: Record<BadgeTone, string> = {
  gray: "bg-gray-800 text-gray-300",
  blue: "bg-blue-600/20 text-blue-300",
  green: "bg-green-600/20 text-green-300",
  red: "bg-red-600/20 text-red-300",
  amber: "bg-amber-600/20 text-amber-300",
};

export function Badge({ tone = "gray", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${badgeTones[tone]}`}>
      {children}
    </span>
  );
}
