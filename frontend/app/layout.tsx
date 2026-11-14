import type { Metadata, Viewport } from "next";
import { Geist } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geist = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "LuminaSkin",
  description: "AI skin triage tuned for Indian and darker skin tones",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, title: "LuminaSkin", statusBarStyle: "default" },
};

export const viewport: Viewport = { themeColor: "#0f766e", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${geist.variable} antialiased min-h-dvh`}>
        <header className="sticky top-0 z-10 bg-background/90 backdrop-blur border-b border-black/5">
          <nav className="mx-auto max-w-md px-4 h-14 flex items-center justify-between">
          <a href="/" className="font-semibold text-brand text-lg">LuminaSkin</a>
          <div className="flex items-center gap-4 text-sm">
            <Link href="/scan" className="font-medium text-brand">New scan</Link>
            <Link href="/history" className="text-black/60">My scans</Link>
          </div>
          </nav>
        </header>
        <main className="mx-auto max-w-md px-4 pb-16">{children}</main>
      </body>
    </html>
  );
}
