import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "ULTRON | AI Operating System", description: "Your secure personal AI assistant platform." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
