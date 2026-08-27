import type { Metadata } from "next";
import { Fraunces, Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const display = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "500", "600", "700"],
});

const sans = Hanken_Grotesk({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["300", "400", "500", "600", "700"],
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "SocialForge AI",
  description: "Multi-brand social media intelligence & content automation.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${sans.variable} ${mono.variable}`}>
        <header className="sf-header">
          <div className="sf-header-inner">
            <Link href="/" className="sf-wordmark">
              SocialForge<span>AI</span>
            </Link>
            <nav className="sf-nav">
              <Link href="/">Brands</Link>
              <Link href="/settings">Settings</Link>
            </nav>
          </div>
        </header>
        <main className="sf-shell">{children}</main>
      </body>
    </html>
  );
}