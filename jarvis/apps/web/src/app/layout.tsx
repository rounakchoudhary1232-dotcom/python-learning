import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "JARVIS | Assistant Console", description: "JARVIS personal AI assistant platform" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
