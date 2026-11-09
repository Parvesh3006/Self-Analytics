"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileUp, LockKeyhole, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { clsx } from "clsx";
import { SourceStamp } from "@/components/postmark";
import { useMoney } from "@/components/providers";
import { Empty, ErrorNote, Notice, PageTitle, Panel, RankBars, Rows, Tabs } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { WORKPLACE, count, place } from "@/lib/format";

export default function CvPage() {
  const client = useQueryClient();
  const profiles = useApi<any[]>("/api/cv");
  const [activeId, setActiveId] = useState<number | null>(null);
  const active = profiles.data?.find((p) => p.id === activeId) ?? profiles.data?.[0];
  const refresh = () => client.invalidateQueries({ queryKey: ["/api/cv"] });
  const remove = useMutation({ mutationFn: (id: number) => api(`/api/cv/${id}`, { method: "DELETE" }), onSuccess: () => { setActiveId(null); refresh(); } });

  return (
    <>
      <PageTitle title="My CV" note="Drop in a CV to see which collected jobs suit it, why, and which skills would open up more." />
      {profiles.isLoading ? <Panel><Rows /></Panel> : profiles.isError ? <Panel><ErrorNote error={profiles.error} retry={profiles.refetch} /></Panel> : !active ? (
        <DropZone onDone={(id) => { setActiveId(id); refresh(); }} large />
      ) : (
        <div className="grid xl:grid-cols-[20rem_minmax(0,1fr)] gap-4 items-start">
          <div className="space-y-4 xl:sticky xl:top-20">
            <Summary profile={active} onDelete={() => remove.mutate(active.id)} deleting={remove.isPending} />
            {profiles.data!.length > 1 && (
              <Panel title="Saved CVs">
                <ul className="space-y-1">{profiles.data!.map((p) => <li key={p.id}><button onClick={() => setActiveId(p.id)} className={clsx("w-full text-left truncate px-2 py-1 rounded-[3px] hover:bg-sheet-2", p.id === active.id && "bg-air-blue-wash font-semibold")}>{p.label}</button></li>)}</ul>
              </Panel>
            )}
            <DropZone onDone={(id) => { setActiveId(id); refresh(); }} />
          </div>
          <Matches cvId={active.id} semantic={active.semantic} />
        </div>
      )}
    </>
  );
}

function DropZone({ onDone, large }: { onDone: (id: number) => void; large?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const upload = useMutation({
    mutationFn: (file: File) => { const body = new FormData(); body.append("file", file); return api("/api/cv", { method: "POST", body }); },
    onSuccess: (profile) => onDone(profile.id),
  });
  const pick = (files: FileList | null) => { if (files?.[0]) upload.mutate(files[0]); };
  return (
    <div>
      <div onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files); }}
        className={clsx("panel border-2 border-dashed text-center transition-colors", large ? "py-16 px-6" : "p-4", over ? "border-air-blue bg-air-blue-wash" : "border-line-strong")}>
        <FileUp size={large ? 30 : 20} strokeWidth={1.5} className="mx-auto text-air-blue" aria-hidden />
        <p className={clsx("font-semibold mt-2", large && "text-lg")}>{upload.isPending ? "Reading your CV" : large ? "Drop your CV here" : "Add another CV"}</p>
        <p className="text-ink-2 text-[0.8125rem] mt-0.5">PDF, DOCX or TXT, up to 8 MB</p>
        <button className="btn btn-primary mt-3" disabled={upload.isPending} onClick={() => input.current?.click()}>{upload.isPending ? "Analysing..." : "Choose a file"}</button>
        <input ref={input} type="file" accept=".pdf,.docx,.txt,.md" className="hidden" onChange={(e) => pick(e.target.files)} />
        {upload.isError && <p role="alert" className="text-bad mt-2 font-medium">{(upload.error as Error).message}</p>}
      </div>
      {large && <p className="flex items-center justify-center gap-1.5 text-[0.8125rem] text-ink-2 mt-3"><LockKeyhole size={14} aria-hidden />Your CV is read on this computer by the local model. It is never sent to a cloud service.</p>}
    </div>
  );
}

function Summary({ profile, onDelete, deleting }: { profile: any; onDelete: () => void; deleting: boolean }) {
  const p = profile.parsed;
  return (
    <Panel>
      <h2 className="text-lg font-bold leading-snug">{p.headline ?? profile.filename}</h2>
      <dl className="text-[0.8125rem] text-ink-2 mt-1 flex gap-4">
        {p.years_experience != null && <div><dt className="inline">Experience: </dt><dd className="inline font-semibold text-ink">{p.years_experience} years</dd></div>}
        <div><dt className="inline">Level: </dt><dd className="inline font-semibold text-ink">{p.seniority}</dd></div>
      </dl>
      {p.summary && <p className="mt-2.5">{p.summary}</p>}
      {p.target_roles?.length > 0 && <><h3 className="font-semibold mt-3 text-[0.8125rem]">Roles matched against</h3><p className="text-[0.8125rem]">{p.target_roles.join(", ")}</p></>}
      <h3 className="font-semibold mt-3 text-[0.8125rem]">Skills found ({p.skills.length})</h3>
      <div className="flex flex-wrap gap-1 mt-1">{p.skills.map((s: string) => <span key={s} className="chip chip-have">{s}</span>)}{p.skills.length === 0 && <span className="text-ink-2 text-[0.8125rem]">None recognised.</span>}</div>
      <div className="flex items-center justify-between gap-2 mt-3 pt-3 border-t border-line">
        <p className="text-xs text-ink-2 flex items-center gap-1 min-w-0"><LockKeyhole size={12} aria-hidden className="shrink-0" /><span className="truncate">{profile.filename}</span></p>
        <button className="btn !h-7 !px-2 text-xs text-bad" disabled={deleting} onClick={onDelete}><Trash2 size={13} aria-hidden />Delete</button>
      </div>
    </Panel>
  );
}

function Matches({ cvId, semantic }: { cvId: number; semantic: boolean }) {
  const f = useFilters();
  const { money } = useMoney();
  const [tab, setTab] = useState("jobs");
  const { data, isLoading, isError, error, refetch, isPlaceholderData } = useApi(`/api/cv/${cvId}/matches?limit=50${f.query ? `&${f.query}` : ""}`);
  if (isLoading) return <Panel><Rows n={10} /></Panel>;
  if (isError) return <Panel><ErrorNote error={error} retry={refetch} /></Panel>;
  return (
    <div className={clsx("space-y-3 transition-opacity", isPlaceholderData && "opacity-60")}>
      <Panel>
        <h2 className="text-lg font-bold">{count(data.strong)} strong {data.strong === 1 ? "match" : "matches"}</h2>
        <p className="panel-note">From {count(data.considered)} jobs that share skills or experience with this CV. Use the filters above to focus on a country, salary or work type.</p>
        <div className="mt-2"><Tabs value={tab} onChange={setTab} tabs={[{ value: "jobs", label: "Best jobs", count: data.matches.length }, { value: "gaps", label: "Skills to add", count: data.gaps.length }, { value: "markets", label: "Best markets", count: data.markets.length }]} /></div>
        {!semantic && <div className="mt-3"><Notice>Matching by skills only. Start Ollama with the bge-m3 model and upload again to also compare the meaning of your experience.</Notice></div>}
      </Panel>
      {tab === "jobs" && (data.matches.length ? <ul className="space-y-2">{data.matches.map((m: any) => <MatchRow key={m.job.id} m={m} cvId={cvId} money={money} />)}</ul> : <Panel><Empty title="No matching jobs">Clear a filter, or add more jobs from Sources.</Empty></Panel>)}
      {tab === "gaps" && (
        <Panel title="Skills that would open up the most jobs" note="Skills named by your strong matches that were not found in your CV. If you do have one, add it to your CV.">
          {data.gaps.length ? <RankBars valueLabel="Missing skills" rows={data.gaps.map((g: any) => ({ label: g.skill, value: g.jobs, display: `${g.share}%`, hint: `${count(g.jobs)} jobs` }))} /> : <Empty title="No gaps found yet">This needs strong matches to compare against.</Empty>}
        </Panel>
      )}
      {tab === "markets" && (
        <Panel title="Where your strong matches are" note="Salary is the median among matches that state pay.">
          {data.markets.length ? <RankBars valueLabel="Strong matches by market" rows={data.markets.map((m: any) => ({ label: m.country, value: m.matches, hint: m.median_usd ? money(m.median_usd) : "pay not stated" }))} /> : <Empty title="No strong matches yet" />}
        </Panel>
      )}
    </div>
  );
}

function MatchRow({ m, cvId, money }: { m: any; cvId: number; money: (v: number | null | undefined) => string }) {
  const j = m.job;
  const explain = useMutation({ mutationFn: () => api(`/api/cv/${cvId}/explain/${j.id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ matched: m.matched, missing: m.missing }) }) });
  return (
    <li className="panel p-3.5 grid grid-cols-[3.25rem_minmax(0,1fr)] gap-3">
      <div className="text-center" aria-label={`Match score ${m.score} out of 100`}>
        <div className="text-[1.375rem] font-bold leading-7 tnum text-air-blue">{m.score}</div>
        <div className="h-1 bg-sheet-2 rounded-full overflow-hidden mt-1"><div className="h-full bg-s1" style={{ width: `${m.score}%` }} /></div>
        <div className="text-2xs text-ink-3 mt-0.5">of 100</div>
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4">
          <Link href={`/jobs/${j.id}`} className="font-semibold text-[0.9375rem] hover:underline">{j.title}</Link>
          <span className="font-semibold tnum whitespace-nowrap">{j.salary_usd_min ? money(j.salary_usd_min) : ""}</span>
        </div>
        <p className="text-ink-2 text-[0.8125rem]">{j.company} · {place(j)} · {WORKPLACE[j.workplace]}</p>
        <ul className="text-[0.8125rem] mt-1.5">{m.reasons.map((r: string) => <li key={r}>{r}</li>)}</ul>
        <div className="flex flex-wrap gap-1 mt-2">
          {m.matched.slice(0, 10).map((s: string) => <span key={s} className="chip chip-have">{s}</span>)}
          {m.missing.slice(0, 6).map((s: string) => <span key={s} className="chip chip-miss" title="Not found in your CV">{s}</span>)}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 mt-2.5">
          <SourceStamp source={j.source} date={j.last_seen} />
          <span className="flex gap-1.5">
            <button className="btn !h-7 text-xs" disabled={explain.isPending} onClick={() => explain.mutate()}>{explain.isPending ? "Writing..." : "Explain this match"}</button>
            {j.apply_url && <a className="btn btn-primary !h-7 text-xs" href={j.apply_url} target="_blank" rel="noreferrer">Open posting</a>}
          </span>
        </div>
        {explain.data && <p className="mt-2.5 pt-2.5 border-t border-line max-w-[75ch]">{explain.data.text}</p>}
        {explain.isError && <p role="alert" className="mt-2 text-bad text-[0.8125rem]">{(explain.error as Error).message}</p>}
      </div>
    </li>
  );
}
