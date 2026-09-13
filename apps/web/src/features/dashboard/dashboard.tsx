"use client";

import { motion } from "framer-motion";
import { Activity, BarChart3, Bot, BookOpen, Code2, FileText, FolderKanban, LayoutDashboard, Link2, Menu, Mic, Paperclip, Plus, Search, Send, Settings, Sparkles, Workflow, X, Zap } from "lucide-react";
import { useState } from "react";
import { JarvisLogo } from "@/components/brand/jarvis-logo";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { cn } from "@/lib/utils";

const navItems = [
  [LayoutDashboard, "Dashboard"], [Plus, "New Task"], [Activity, "Conversations"], [FolderKanban, "Projects"], [FileText, "Files"], [Search, "Research"], [Code2, "Code"], [BarChart3, "Data Analysis"], [Workflow, "Automations"], [BookOpen, "Memory"], [Settings, "Settings"]
] as const;
const quickActions = [
  [BarChart3, "Analyze Data", "Explore a dataset"], [Code2, "Write Code", "Build with confidence"], [Search, "Research", "Compare trusted sources"], [FileText, "Analyze File", "Extract useful context"], [Sparkles, "Create Document", "Draft from an idea"], [Workflow, "Automate Task", "Design a workflow"]
] as const;
const recentActivity = [
  ["Research workspace", "Source synthesis prepared", "12 min ago"], ["Portfolio review", "Project context updated", "Yesterday"], ["Quarterly planning", "Document draft created", "Tue"]
] as const;
const systemStatus = [["ULTRON Online", "active"], ["AI Core — Ready", "ready"], ["Memory — Active", "active"], ["Voice — Ready", "ready"], ["Vision — Ready", "ready"], ["Tools — Connected", "active"], ["System — Operational", "active"]] as const;

function Sidebar({ open, close }: { open: boolean; close: () => void }) {
  return <aside className={cn("fixed inset-y-0 left-0 z-30 flex w-72 flex-col border-r border-white/[.08] bg-[#0b0e14]/95 px-4 py-5 backdrop-blur-xl transition-transform lg:static lg:translate-x-0", open ? "translate-x-0" : "-translate-x-full")}>
    <div className="flex items-center justify-between px-2"><JarvisLogo /><button onClick={close} className="rounded-md p-2 text-slate-400 lg:hidden" aria-label="Close navigation"><X size={18} /></button></div>
    <nav className="mt-9 space-y-1" aria-label="Primary navigation">{navItems.map(([Icon, label], index) => <button key={label} className={cn("flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition", index === 0 ? "bg-cyan/10 text-cyan" : "text-slate-400 hover:bg-white/[.04] hover:text-slate-200")}><Icon size={17} strokeWidth={1.7} />{label}</button>)}</nav>
    <div className="mt-auto rounded-xl border border-cyan/15 bg-cyan/[.045] p-4"><div className="flex items-center gap-2 text-xs font-medium text-cyan"><Zap size={14} />SYSTEM STATUS</div><p className="mt-2 text-xs leading-5 text-slate-400">All systems are ready for your next command.</p><div className="mt-3"><StatusIndicator label="Operational" tone="active" /></div></div>
  </aside>;
}

export function Dashboard() {
  const [menuOpen, setMenuOpen] = useState(false);
  return <main className="grid-background flex min-h-screen bg-[#090b10]"><Sidebar open={menuOpen} close={() => setMenuOpen(false)} />{menuOpen && <button onClick={() => setMenuOpen(false)} aria-label="Close navigation overlay" className="fixed inset-0 z-20 bg-black/60 lg:hidden" />}
    <div className="min-w-0 flex-1"><header className="flex h-20 items-center justify-between border-b border-white/[.06] px-5 sm:px-8"><button onClick={() => setMenuOpen(true)} className="rounded-lg p-2 text-slate-300 lg:hidden" aria-label="Open navigation"><Menu /></button><div className="hidden lg:block"><StatusIndicator label="Secure workspace" /></div><div className="ml-auto flex items-center gap-3"><button className="rounded-lg border border-white/[.08] p-2 text-slate-400" aria-label="Notifications are unavailable in Phase 1" title="Available in a future phase"><Link2 size={17} /></button><div className="flex items-center gap-2 rounded-full border border-white/[.08] bg-white/[.03] py-1 pl-1 pr-3"><span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-cyan to-blue-500 text-xs font-bold text-slate-950">S</span><span className="text-xs text-slate-300">Sir</span></div></div></header>
      <div className="mx-auto max-w-7xl px-5 py-10 sm:px-8 lg:px-12"><motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .35 }}>
        <p className="text-sm font-medium tracking-[.18em] text-cyan">COMMAND CENTER</p><h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Good evening, Sir.</h1><p className="mt-2 text-base text-slate-400">How can I assist you today?</p>
      </motion.div>
      <CommandBar />
      <section className="mt-10"><div className="mb-4 flex items-end justify-between"><div><h2 className="text-lg font-semibold text-slate-100">Start with a capability</h2><p className="mt-1 text-sm text-slate-400">Choose a workspace to focus your next request.</p></div><span className="hidden text-xs text-slate-500 sm:block">Phase 1 previews</span></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{quickActions.map(([Icon, title, description], index) => <motion.button initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .04 }} key={title} className="group text-left" title="This capability will be implemented in a future phase"><GlassCard className="h-full p-5 transition duration-200 group-hover:-translate-y-0.5 group-hover:border-cyan/25"><Icon size={19} className="text-cyan" strokeWidth={1.6}/><h3 className="mt-4 font-medium text-slate-100">{title}</h3><p className="mt-1 text-sm text-slate-400">{description}</p></GlassCard></motion.button>)}</div></section>
      <section className="mt-10 grid gap-5 lg:grid-cols-[1.25fr_.75fr]"><GlassCard className="p-5 sm:p-6"><SectionHeading title="Recent Activity" subtitle="A concise view of work across your workspace." /><div className="mt-5 divide-y divide-white/[.06]">{recentActivity.map(([title, detail, time]) => <div key={title} className="flex items-center gap-4 py-4 first:pt-0 last:pb-0"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white/[.045] text-cyan"><Activity size={16}/></span><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-slate-200">{title}</p><p className="mt-0.5 truncate text-xs text-slate-500">{detail}</p></div><time className="text-xs text-slate-500">{time}</time></div>)}</div></GlassCard>
      <GlassCard className="p-5 sm:p-6"><SectionHeading title="System Status" subtitle="Presentation-only readiness signals." /><div className="mt-5 grid grid-cols-2 gap-y-4">{systemStatus.map(([label, tone]) => <StatusIndicator key={label} label={label} tone={tone} />)}</div></GlassCard></section>
      </div></div></main>;
}

function SectionHeading({ title, subtitle }: { title: string; subtitle: string }) { return <div><h2 className="text-lg font-semibold text-slate-100">{title}</h2><p className="mt-1 text-sm text-slate-400">{subtitle}</p></div>; }
function CommandBar() { return <GlassCard className="mt-8 overflow-hidden border-cyan/15 p-2 shadow-glow"><div className="flex items-center gap-2 rounded-xl bg-black/15 px-3 py-2"><Sparkles className="shrink-0 text-cyan" size={20}/><input aria-label="Ask ULTRON anything" placeholder="Ask ULTRON anything..." className="min-w-0 flex-1 bg-transparent py-2 text-sm text-slate-100 outline-none placeholder:text-slate-500" /><button title="Voice input arrives in Phase 7" aria-label="Voice input unavailable" className="rounded-lg p-2 text-slate-400 hover:bg-white/[.05]"><Mic size={18}/></button><button title="Attachments arrive in Phase 5" aria-label="Attachment unavailable" className="rounded-lg p-2 text-slate-400 hover:bg-white/[.05]"><Paperclip size={18}/></button><button title="Conversation delivery arrives in Phase 3" aria-label="Send unavailable" className="rounded-lg bg-cyan p-2 text-slate-950"><Send size={17}/></button></div><div className="flex items-center justify-between px-3 pb-1 pt-2"><span className="text-[11px] text-slate-500">Commands are not sent during Phase 1.</span><button title="Voice mode arrives in Phase 7" className="text-[11px] font-medium text-cyan">Voice mode</button></div></GlassCard>; }
