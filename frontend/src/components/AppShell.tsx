"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

type Brand = "fieldpie" | "evatro";
type Theme = "light" | "dark";

const BRAND_LABEL: Record<Brand, { name: string; lang: string }> = {
  fieldpie: { name: "FieldPie", lang: "EN" },
  evatro: { name: "Evatro", lang: "TR" },
};

function IconGrid() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  );
}
function IconPipeline() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 6h16M4 12h16M4 18h10" />
      <circle cx="19" cy="18" r="2.4" fill="currentColor" stroke="none" />
    </svg>
  );
}
function IconCalendar() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 9h18M8 4v16" />
    </svg>
  );
}
function IconAssets() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M4 15l4-4 3 3 5-6 4 5" />
    </svg>
  );
}
function IconSettings() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" />
    </svg>
  );
}
function IconMoon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z" />
    </svg>
  );
}
function IconSun() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="4.5" />
      <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M19.4 4.6l-1.8 1.8M6.4 17.6l-1.8 1.8" />
    </svg>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const [brand, setBrand] = useState<Brand>("fieldpie");
  const [theme, setTheme] = useState<Theme>("light");
  const [mounted, setMounted] = useState(false);

  // Read what the no-flash init script already applied to <html>.
  useEffect(() => {
    const root = document.documentElement;
    const b = (root.getAttribute("data-brand") as Brand) || "fieldpie";
    setBrand(b === "evatro" ? "evatro" : "fieldpie");
    const explicit = root.getAttribute("data-theme") as Theme | null;
    const isDark = explicit
      ? explicit === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    setTheme(isDark ? "dark" : "light");
    setMounted(true);
  }, []);

  function chooseBrand(b: Brand) {
    setBrand(b);
    document.documentElement.setAttribute("data-brand", b);
    try {
      localStorage.setItem("sf-brand", b);
    } catch {}
  }
  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("sf-theme", next);
    } catch {}
  }

  const onBrands = pathname === "/" || pathname.startsWith("/brands");
  const onPipeline = /^\/brands\/[^/]+\/pipeline/.test(pathname);
  const onSettings = pathname.startsWith("/settings");

  // Contextual pipeline link if we are inside a brand route.
  const brandMatch = pathname.match(/^\/brands\/([^/]+)/);
  const pipelineHref = brandMatch ? `/brands/${brandMatch[1]}/pipeline` : null;

  const section = onSettings ? "Settings" : onPipeline ? "Pipeline" : "Brands";
  const bl = BRAND_LABEL[brand];

  return (
    <div className="sfx-app">
      <aside className="sfx-side">
        <div className="sfx-brandpick">
          <div className="sfx-logo">S</div>
          <div className="sfx-wordmark">
            SocialForge
            <small>Content Studio</small>
          </div>
        </div>

        <div className="sfx-brandtabs" role="group" aria-label="Active brand accent">
          <button
            className="sfx-brandtab fp"
            aria-pressed={brand === "fieldpie"}
            onClick={() => chooseBrand("fieldpie")}
          >
            <span className="sfx-dot" />
            FieldPie
          </button>
          <button
            className="sfx-brandtab ev"
            aria-pressed={brand === "evatro"}
            onClick={() => chooseBrand("evatro")}
          >
            <span className="sfx-dot" />
            Evatro
          </button>
        </div>

        <div className="sfx-navsec">Workspace</div>
        <nav className="sfx-nav">
          <Link href="/" className={`sfx-navitem${onBrands && !onPipeline ? " active" : ""}`}>
            <IconGrid />
            Brands
          </Link>
          {pipelineHref ? (
            <Link
              href={pipelineHref}
              className={`sfx-navitem${onPipeline ? " active" : ""}`}
            >
              <IconPipeline />
              Content Pipeline
            </Link>
          ) : (
            <span className="sfx-navitem soon" aria-disabled="true">
              <IconPipeline />
              Content Pipeline
              <span className="sfx-soon">brand</span>
            </span>
          )}
          <span className="sfx-navitem soon" aria-disabled="true">
            <IconCalendar />
            Calendar
            <span className="sfx-soon">soon</span>
          </span>
          <span className="sfx-navitem soon" aria-disabled="true">
            <IconAssets />
            Assets
            <span className="sfx-soon">soon</span>
          </span>
        </nav>

        <div className="sfx-navsec">Configure</div>
        <nav className="sfx-nav">
          <Link href="/settings" className={`sfx-navitem${onSettings ? " active" : ""}`}>
            <IconSettings />
            Settings
          </Link>
        </nav>

        <div className="sfx-foot">
          <div className="sfx-avatar">R</div>
          <div>
            <div className="nm">Resul</div>
            <small>Admin</small>
          </div>
        </div>
      </aside>

      <div className="sfx-main">
        <header className="sfx-topbar">
          <div className="sfx-crumb">
            <span>SocialForge</span>
            <span className="sep">/</span>
            <b>{section}</b>
          </div>
          <span className="sfx-brandchip">
            <span className="sfx-dot" />
            {bl.name} · {bl.lang}
          </span>
          <div className="sfx-spacer" />
          <button
            className="sfx-tbtn"
            onClick={toggleTheme}
            aria-label="Toggle color theme"
            suppressHydrationWarning
          >
            {mounted && theme === "dark" ? <IconSun /> : <IconMoon />}
            <span suppressHydrationWarning>
              {mounted ? (theme === "dark" ? "Light" : "Dark") : "Theme"}
            </span>
          </button>
        </header>

        <main className="sfx-content">{children}</main>
      </div>
    </div>
  );
}
