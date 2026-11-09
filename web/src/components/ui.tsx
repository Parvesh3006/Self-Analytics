"use client";

import { AlertTriangle, CircleHelp, Info } from "lucide-react";
import { clsx } from "clsx";
import { useState } from "react";

export function PageTitle({ title, note, children }: { title: string; note?: string; children?: React.ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3 mb-4">
      <div>
        <h1 className="text-[1.625rem] leading-tight font-bold tracking-tight">{title}</h1>
        {note && <p className="text-ink-2 mt-0.5 max-w-[75ch]">{note}</p>}
      </div>
      {children}
    </header>
  );
}

export function Panel({ title, note, action, className, children, dimmed }: { title?: string; note?: string; action?: React.ReactNode; className?: string; children: React.ReactNode; dimmed?: boolean }) {
  return (
    <section className={clsx("panel p-4 transition-opacity duration-200", dimmed && "opacity-60", className)}>
      {(title || action) && (
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            {title && <h2 className="panel-title">{title}</h2>}
            {note && <p className="panel-note mt-0.5">{note}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn"; children: React.ReactNode }) {
  const Icon = tone === "warn" ? AlertTriangle : Info;
  return (
    <p className={clsx("flex items-start gap-2 px-3 py-2 rounded-[4px] text-[0.8125rem]", tone === "warn" ? "bg-warn-wash text-[#5e3e00]" : "bg-air-blue-wash text-rail-deep")}>
      <Icon size={15} className="mt-0.5 shrink-0" aria-hidden /><span>{children}</span>
    </p>
  );
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="py-8 px-4 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="text-ink-2 mt-1 max-w-[52ch] mx-auto">{children}</div>}
    </div>
  );
}

export function ErrorNote({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div role="alert" className="py-6 text-center">
      <p className="font-semibold">This could not load</p>
      <p className="text-ink-2 mt-1">{error instanceof Error ? error.message : "The data service did not respond."}</p>
      {retry && <button className="btn mt-3" onClick={retry}>Try again</button>}
    </div>
  );
}

export function Rows({ n = 6 }: { n?: number }) {
  return <div className="space-y-2.5" aria-busy>{Array.from({ length: n }, (_, i) => <div key={i} className="skeleton h-5" />)}</div>;
}

/** Ranked list with thin bars: label and value stay readable text, and the bar only adds proportion. */
export function RankBars({ rows, onPick, valueLabel }: { rows: { label: string; value: number; display?: string; hint?: string; key?: string; selected?: boolean }[]; onPick?: (key: string) => void; valueLabel?: string }) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <ul className="space-y-0.5" aria-label={valueLabel}>
      {rows.map((row) => {
        const inner = (
          <>
            <span className="flex items-baseline justify-between gap-3">
              <span className={clsx("truncate", row.selected ? "font-bold text-air-blue" : "font-medium")}>{row.label}</span>
              <span className="tnum text-[0.8125rem] whitespace-nowrap"><span className="font-semibold">{row.display ?? row.value.toLocaleString("en")}</span>{row.hint && <span className="text-ink-3 ml-2">{row.hint}</span>}</span>
            </span>
            <span className="block h-1 mt-1 rounded-r-[2px] bg-s1" style={{ width: `${Math.max(1.5, (row.value / max) * 100)}%` }} />
          </>
        );
        return (
          <li key={row.key ?? row.label}>
            {onPick
              ? <button className="block w-full text-left px-1.5 py-1 rounded-[3px] hover:bg-sheet-2 transition-colors" onClick={() => onPick(row.key ?? row.label)}>{inner}</button>
              : <div className="px-1.5 py-1">{inner}</div>}
          </li>
        );
      })}
    </ul>
  );
}

export function Hint({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex align-middle">
      <button type="button" aria-label={text} className="text-ink-3 hover:text-ink" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}>
        <CircleHelp size={13} aria-hidden />
      </button>
      {open && <span role="tooltip" className="absolute left-1/2 -translate-x-1/2 top-5 z-40 w-56 p-2 rounded-[4px] bg-ink text-white text-xs font-normal shadow-pop">{text}</span>}
    </span>
  );
}

export function Tabs({ tabs, value, onChange }: { tabs: { value: string; label: string; count?: number }[]; value: string; onChange: (v: string) => void }) {
  return (
    <div role="tablist" className="flex flex-wrap gap-x-1 border-b border-line">
      {tabs.map((t) => (
        <button key={t.value} role="tab" aria-selected={value === t.value} onClick={() => onChange(t.value)}
          className={clsx("h-9 px-3 -mb-px border-b-2 font-semibold transition-colors", value === t.value ? "border-air-red text-ink" : "border-transparent text-ink-2 hover:text-ink")}>
          {t.label}{t.count != null && <span className="ml-1.5 tnum text-xs text-ink-3">{t.count.toLocaleString("en")}</span>}
        </button>
      ))}
    </div>
  );
}
