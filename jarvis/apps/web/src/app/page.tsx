"use client";
import { useState } from "react";
import { Activity, ChevronRight } from "lucide-react";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { CommandBar } from "@/components/dashboard/command-bar";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { RecentActivity } from "@/components/dashboard/activity";
import { SystemStatus } from "@/components/dashboard/system-status";
export default function DashboardPage(){const [menuOpen,setMenuOpen]=useState(false);return <main className="flex min-h-screen bg-[radial-gradient(ellipse_at_top,rgba(14,116,144,.13),transparent_36%),#080b10]"><Sidebar open={menuOpen} onClose={()=>setMenuOpen(false)}/><div className="min-w-0 flex-1"><TopBar onMenu={()=>setMenuOpen(true)}/><div className="mx-auto max-w-7xl px-5 py-10 sm:px-8 lg:px-12"><div className="mb-10"><div className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-[.18em] text-cyan-300/80"><Activity size={14}/> Command center <ChevronRight size={13}/></div><h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Good evening, Sir.</h1><p className="mt-3 text-base text-slate-400">How can I assist you today?</p></div><div className="max-w-4xl"><CommandBar /></div><div className="mt-10"><QuickActions /></div><div className="mt-10 grid gap-5 xl:grid-cols-[1.3fr_.7fr]"><RecentActivity/><SystemStatus/></div></div></div></main>}
