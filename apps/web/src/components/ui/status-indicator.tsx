import { cn } from "@/lib/utils";
export function StatusIndicator({ label, tone = "ready" }: { label: string; tone?: "ready" | "active" }) {
  return <span className="inline-flex items-center gap-2 text-xs text-slate-300"><i className={cn("h-1.5 w-1.5 rounded-full", tone === "active" ? "bg-cyan shadow-[0_0_8px_#57d8ff]" : "bg-emerald-400")} />{label}</span>;
}
