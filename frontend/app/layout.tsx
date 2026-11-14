import type { Metadata, Viewport } from "next";
import { Fraunces, Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const fraunces = Fraunces({ variable: "--font-fraunces", subsets: ["latin"], style: ["normal", "italic"] });
const hanken = Hanken_Grotesk({ variable: "--font-hanken", subsets: ["latin"] });
const jetbrains = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "LuminaSkin",
  description: "AI skin triage tuned for Indian and darker skin tones",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, title: "LuminaSkin", statusBarStyle: "default" },
};

export const viewport: Viewport = { themeColor: "#F3EFE6", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${fraunces.variable} ${hanken.variable} ${jetbrains.variable} antialiased min-h-dvh flex flex-col`}>
        <header className="sticky top-0 z-10 border-b border-rule bg-background/95 backdrop-blur">
          <nav className="wrap flex min-h-[64px] items-center justify-between gap-6">
            <a href="/" aria-label="LuminaSkin, home" className="font-serif text-[1.45rem] font-semibold leading-none tracking-[-0.02em]">
              Lumina<i className="font-normal">Skin</i>
            </a>
            <div className="flex items-center gap-5 sm:gap-8 text-[0.94rem] font-medium">
              <Link href="/history" className="border-b border-transparent py-1 hover:border-foreground">My scans</Link>
              <Link href="/scan" className="btn btn-ink btn-sm">
                <span className="hidden sm:inline">Start a scan</span><span className="sm:hidden">Scan</span>
                <span className="font-mono font-normal">→</span>
              </Link>
            </div>
          </nav>
        </header>
        <main className="wrap flex-1 pb-20">{children}</main>
        <footer className="border-t border-rule">
          <div className="wrap py-7 text-[0.85rem] text-muted">
            <p><b className="text-foreground">LuminaSkin</b> is a triage aid, not a diagnosis. It has not been clinically validated. Always consult a qualified doctor.</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
