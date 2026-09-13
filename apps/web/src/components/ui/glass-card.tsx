import { cn } from "@/lib/utils";
import type { PropsWithChildren } from "react";

export function GlassCard({ children, className }: PropsWithChildren<{ className?: string }>) {
  return <section className={cn("rounded-2xl border border-white/[.08] bg-slate-900/55 shadow-xl shadow-black/10 backdrop-blur", className)}>{children}</section>;
}
