"use client";

import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { ChevronLeft, ChevronRight, Download } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { clsx } from "clsx";
import { SourceStamp } from "@/components/postmark";
import { useMoney } from "@/components/providers";
import { Empty, ErrorNote, PageTitle, Panel, Rows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { WORKPLACE, count, place } from "@/lib/format";

const SORTABLE: Record<string, string> = { title: "title", company: "company", salary: "salary", posted: "newest" };
const column = createColumnHelper<any>();

export default function JobsPage() {
  const f = useFilters();
  const params = useSearchParams();
  const router = useRouter();
  const { money } = useMoney();
  const page = Number(params.get("page") ?? 1);
  const sort = params.get("sort") ?? "newest";
  const { data, isLoading, isError, error, refetch, isPlaceholderData } = useApi(`/api/jobs?page=${page}&size=25&sort=${sort}${f.query ? `&${f.query}` : ""}`);

  const setParam = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(changes)) next.set(k, v);
    router.replace(`/jobs?${next}`, { scroll: false });
  };

  const columns = useMemo(() => [
    column.accessor("title", { id: "title", header: "Job", cell: (c) => {
      const j = c.row.original;
      return <div className="min-w-64"><Link href={`/jobs/${j.id}`} className="font-semibold hover:underline">{j.title}</Link><div className="flex flex-wrap gap-1 mt-1">{j.skills.slice(0, 5).map((s: string) => <span key={s} className="chip">{s}</span>)}</div></div>;
    } }),
    column.accessor("company", { id: "company", header: "Company", cell: (c) => <span className="font-medium">{c.getValue()}</span> }),
    column.display({ id: "location", header: "Location", cell: (c) => <div className="min-w-36">{place(c.row.original)}<div className="text-xs text-ink-2">{WORKPLACE[c.row.original.workplace]}</div></div> }),
    column.accessor("salary_usd_min", { id: "salary", header: "Salary", cell: (c) => {
      const j = c.row.original;
      return j.salary_usd_min ? <span className="tnum font-semibold whitespace-nowrap">{money(j.salary_usd_min)}{j.salary_usd_max ? ` to ${money(j.salary_usd_max)}` : ""}</span> : <span className="text-ink-3">Not stated</span>;
    } }),
    column.accessor("posted_at", { id: "posted", header: "Posted", cell: (c) => {
      const j = c.row.original;
      return <span className="tnum whitespace-nowrap">{new Date(j.posted_at ?? j.first_seen).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}</span>;
    } }),
    column.display({ id: "source", header: "Source", cell: (c) => <SourceStamp source={c.row.original.source} date={c.row.original.last_seen} /> }),
  ], [money]);

  const table = useReactTable({ data: data?.jobs ?? [], columns, getCoreRowModel: getCoreRowModel(), manualPagination: true, manualSorting: true });
  const pages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1;

  return (
    <>
      <PageTitle title="Jobs" note={data ? `${count(data.total)} open jobs match your filters.` : undefined}>
        <a className="btn" href={`/api/jobs/export.csv${f.query ? `?${f.query}` : ""}`}><Download size={14} aria-hidden />Export CSV</a>
      </PageTitle>
      <Panel className="!p-0 overflow-hidden" dimmed={isPlaceholderData}>
        {isLoading ? <div className="p-4"><Rows n={14} /></div> : isError ? <ErrorNote error={error} retry={refetch} /> : data.jobs.length === 0 ? <Empty title="No jobs match these filters">Remove a filter or widen the date range.</Empty> : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>{table.getHeaderGroups().map((group) => <tr key={group.id}>{group.headers.map((h) => {
                const key = SORTABLE[h.column.id];
                const on = sort === key;
                return <th key={h.id} aria-sort={on ? (key === "title" || key === "company" ? "ascending" : "descending") : undefined}>{key ? <button onClick={() => setParam({ sort: key, page: "1" })} className={clsx("hover:text-ink", on && "text-ink underline underline-offset-4 decoration-air-red decoration-2")}>{flexRender(h.column.columnDef.header, h.getContext())}</button> : flexRender(h.column.columnDef.header, h.getContext())}</th>;
              })}</tr>)}</thead>
              <tbody>{table.getRowModel().rows.map((row) => <tr key={row.id}>{row.getVisibleCells().map((cell) => <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>)}</tbody>
            </table>
          </div>
        )}
      </Panel>
      {data && data.total > 0 && (
        <nav aria-label="Pages" className="flex items-center justify-end gap-2 mt-3">
          <span className="tnum text-[0.8125rem] text-ink-2">Page {count(page)} of {count(pages)}</span>
          <button className="btn" disabled={page <= 1} onClick={() => setParam({ page: String(page - 1) })}><ChevronLeft size={15} aria-hidden />Previous</button>
          <button className="btn" disabled={page >= pages} onClick={() => setParam({ page: String(page + 1) })}>Next<ChevronRight size={15} aria-hidden /></button>
        </nav>
      )}
    </>
  );
}
