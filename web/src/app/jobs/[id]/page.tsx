"use client";

import { ArrowLeft, ExternalLink } from "lucide-react";
import Link from "next/link";
import { use } from "react";
import { Postmark } from "@/components/postmark";
import { useMoney } from "@/components/providers";
import { ErrorNote, Notice, Panel, Rows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { WORKPLACE, originalPay, place, shortDate } from "@/lib/format";

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { money } = useMoney();
  const { data: j, isLoading, isError, error, refetch } = useApi(`/api/jobs/${id}`);
  if (isLoading) return <Panel><Rows n={12} /></Panel>;
  if (isError) return <Panel><ErrorNote error={error} retry={refetch} /></Panel>;
  const pay = originalPay(j);
  const specs: [string, React.ReactNode][] = [
    ["Salary", j.salary_usd_min ? <>{money(j.salary_usd_min)}{j.salary_usd_max ? ` to ${money(j.salary_usd_max)}` : ""} a year{pay && <span className="block text-xs text-ink-2 font-normal">Advertised as {pay}</span>}</> : "Not stated"],
    ["Location", place(j)], ["Work type", WORKPLACE[j.workplace]], ["Role", j.role_family], ["Level", j.seniority], ["Employment", j.employment_type ?? "Not stated"],
    ["Visa sponsorship", j.visa_sponsorship === true ? "Mentioned as available" : j.visa_sponsorship === false ? "Posting says not available" : "Not mentioned"],
    ["Posted", shortDate(j.posted_at ?? j.first_seen)], ["Last seen open", shortDate(j.last_seen)],
  ];

  return (
    <div className="max-w-6xl">
      <Link href="/jobs" className="inline-flex items-center gap-1 text-air-blue font-medium hover:underline mb-3"><ArrowLeft size={15} aria-hidden />All jobs</Link>
      <div className="grid lg:grid-cols-[minmax(0,1fr)_20rem] gap-4 items-start">
        <div className="space-y-4">
          <Panel>
            <h1 className="text-[1.625rem] leading-tight font-bold tracking-tight">{j.title}</h1>
            <p className="text-[1rem] text-ink-2 mt-0.5">{j.company} · {place(j)}</p>
            {!j.is_active && <div className="mt-3"><Notice tone="warn">This job has not been seen recently and may be closed.</Notice></div>}
            {j.apply_url && <a href={j.apply_url} target="_blank" rel="noreferrer" className="btn btn-primary mt-3">Open original posting<ExternalLink size={14} aria-hidden /></a>}
          </Panel>
          <Panel title="Skills named in this job">
            <div className="flex flex-wrap gap-1">{j.skills.map((s: string) => <Link key={s} className="chip hover:border-air-blue" href={`/jobs?skill=${encodeURIComponent(s)}`}>{s}</Link>)}{j.skills.length === 0 && <span className="panel-note">None recognised in this posting.</span>}</div>
          </Panel>
          <Panel title="Job description">{j.description ? <div className="prose-job">{j.description}</div> : <p className="panel-note">This source does not publish a description. Open the original posting to read it.</p>}</Panel>
        </div>
        <div className="space-y-4 lg:sticky lg:top-6">
          <Panel title="Specification">
            <dl className="space-y-2">{specs.map(([k, v]) => <div key={k} className="grid grid-cols-[6.75rem_1fr] gap-2"><dt className="text-[0.8125rem] text-ink-2">{k}</dt><dd className="font-medium">{v}</dd></div>)}</dl>
          </Panel>
          <Panel title="Where this was collected" note={j.sightings.length > 1 ? `Found on ${j.sightings.length} sources and merged into one job.` : undefined}>
            <ul className="flex flex-wrap gap-3">{j.sightings.map((s: any) => <li key={s.source}>{s.url ? <a href={s.url} target="_blank" rel="noreferrer" title={`Open on ${s.source}`}><Postmark source={s.source} date={s.last_seen} size={84} /></a> : <Postmark source={s.source} date={s.last_seen} size={84} />}</li>)}</ul>
          </Panel>
          {j.similar.length > 0 && <Panel title="Similar jobs"><ul className="space-y-2.5">{j.similar.map((s: any) => <li key={s.id}><Link href={`/jobs/${s.id}`} className="font-medium hover:underline">{s.title}</Link><p className="text-xs text-ink-2">{s.company} · {place(s)}</p></li>)}</ul></Panel>}
        </div>
      </div>
    </div>
  );
}
