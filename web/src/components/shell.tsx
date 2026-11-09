"use client";

import { useIsFetching } from "@tanstack/react-query";
import { BriefcaseBusiness, FileUser, Globe2, Library, MessageCircleQuestion, RadioTower, TrendingUp } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { useApi } from "@/lib/api";
import { CURRENCIES, count, timeAgo } from "@/lib/format";
import { FilterBar } from "./filter-bar";
import { useMoney } from "./providers";

const NAV = [
  { href: "/", label: "Markets", icon: Globe2 },
  { href: "/cv", label: "My CV", icon: FileUser },
  { href: "/skills", label: "Skills", icon: TrendingUp },
  { href: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { href: "/assistant", label: "Ask AI", icon: MessageCircleQuestion },
  { href: "/reports", label: "Reports", icon: Library },
  { href: "/sources", label: "Sources", icon: RadioTower },
];
const FILTERED = ["/", "/cv", "/skills", "/jobs"];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const fetching = useIsFetching();
  const { currency, setCurrency } = useMoney();
  const { data: status } = useApi("/api/status", 60_000);
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <div className="lg:grid lg:grid-cols-[13rem_minmax(0,1fr)] min-h-dvh">
      <aside className="bg-rail text-rail-ink flex flex-col lg:sticky lg:top-0 lg:h-dvh z-30">
        <div className="airmail-edge" aria-hidden />
        <div className="px-4 pt-4 pb-3 flex items-center justify-between lg:block">
          <Link href="/" className="block text-white font-bold text-lg tracking-tight">Self Analytics</Link>
          <p className="hidden lg:block text-xs text-rail-muted mt-0.5">Your job-market desk</p>
        </div>
        <nav aria-label="Main" className="flex lg:flex-col gap-0.5 px-2 pb-2 overflow-x-auto">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} aria-current={isActive(href) ? "page" : undefined}
              className={clsx("flex items-center gap-2.5 px-2.5 h-9 rounded-[4px] font-medium whitespace-nowrap transition-colors",
                isActive(href) ? "bg-white text-rail" : "hover:bg-rail-deep text-rail-ink")}>
              <Icon size={17} strokeWidth={1.75} aria-hidden />{label}
            </Link>
          ))}
        </nav>
        <div className="hidden lg:block mt-auto px-4 py-4 space-y-3 text-xs border-t border-white/15">
          <label className="block">
            <span className="text-rail-muted">Show salaries in</span>
            <select value={currency} onChange={(e) => setCurrency(e.target.value)} className="mt-1 w-full h-8 px-2 rounded-[4px] bg-rail-deep border border-white/25 text-white">
              {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
          <p className="text-rail-muted leading-relaxed">
            <span className="text-white font-semibold tnum">{count(status?.jobs)}</span> open jobs<br />
            Updated {timeAgo(status?.last_collected)}
          </p>
        </div>
      </aside>
      <div className="min-w-0 flex flex-col">
        <div className={clsx("h-[3px] sticky top-0 z-20", fetching > 0 && "airmail-edge airmail-transit")} aria-hidden />
        {FILTERED.includes(pathname) && <FilterBar />}
        <main className="flex-1 px-4 lg:px-6 py-5 max-w-[1500px] w-full">{children}</main>
      </div>
    </div>
  );
}
