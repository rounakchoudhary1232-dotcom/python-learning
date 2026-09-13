import { cn } from "@/lib/utils";

export function JarvisLogo({ compact = false }: { compact?: boolean }) {
  return <div className="flex items-center gap-3" aria-label="ULTRON">
    <span className="grid h-9 w-9 place-items-center rounded-xl border border-cyan/40 bg-cyan/10 shadow-glow">
      <span className="h-3 w-3 rotate-45 rounded-sm border border-cyan bg-cyan/30" />
    </span>
    {!compact && <span className={cn("text-sm font-semibold tracking-[.24em] text-slate-100")}>ULTRON</span>}
  </div>;
}
