import { cn } from "@/lib/utils";
export function GlassCard({ children, className }: React.PropsWithChildren<{ className?: string }>) { return <section className={cn("rounded-2xl border border-white/[0.08] bg-white/[0.035] shadow-[0_18px_50px_rgba(0,0,0,0.18)] backdrop-blur-sm", className)}>{children}</section>; }
