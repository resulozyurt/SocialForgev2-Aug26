import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import AppShell from "@/components/AppShell";

const display = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["600", "700", "800"],
});

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["400", "500", "600"],
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

// Set theme + brand before first paint so there is no flash of the wrong palette.
const themeInit = `(function(){try{var t=localStorage.getItem('sf-theme');if(t==='dark'||t==='light')document.documentElement.setAttribute('data-theme',t);var b=localStorage.getItem('sf-brand');document.documentElement.setAttribute('data-brand',(b==='evatro'||b==='fieldpie')?b:'fieldpie');}catch(e){document.documentElement.setAttribute('data-brand','fieldpie');}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body className={`${display.variable} ${sans.variable} ${mono.variable}`}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
