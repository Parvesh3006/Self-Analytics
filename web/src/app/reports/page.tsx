"use client";

import { useState } from "react";
import { Postmark } from "@/components/postmark";
import { Empty, ErrorNote, PageTitle, Panel, Rows } from "@/components/ui";
import { useApi } from "@/lib/api";

export default function ReportsPage() {
  const [search, setSearch] = useState("");
  const { data, isLoading, isError, error, refetch } = useApi<any[]>(`/api/insights${search ? `?q=${encodeURIComponent(search)}` : ""}`);
  return (
    <>
      <PageTitle title="Reports" note="Summaries of labour-market statistics and research from your trend sources. These feed the assistant and are never counted as job postings.">
        <input aria-label="Search reports" className="field w-64" placeholder="Search reports" value={search} onChange={(e) => setSearch(e.target.value)} />
      </PageTitle>
      {isLoading ? <Panel><Rows n={10} /></Panel> : isError ? <Panel><ErrorNote error={error} retry={refetch} /></Panel> : !data?.length ? (
        <Panel><Empty title={search ? "No reports match that search" : "No reports collected yet"}>{!search && "Reports are read from the statistics sites in Sources on a monthly schedule."}</Empty></Panel>
      ) : (
        <ul className="grid lg:grid-cols-2 gap-3">
          {data.map((r) => (
            <li key={r.id} className="panel p-4 flex gap-3">
              <div className="min-w-0 flex-1">
                <a href={r.url} target="_blank" rel="noreferrer" className="font-semibold text-[0.9375rem] hover:underline">{r.title}</a>
                <p className="mt-1.5 text-[0.8125rem] leading-relaxed line-clamp-6">{r.summary}</p>
              </div>
              <Postmark source={r.source} date={r.fetched_at} detail={r.region ?? undefined} size={68} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
