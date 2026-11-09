"use client";

import * as Popover from "@radix-ui/react-popover";
import { Command } from "cmdk";
import { Check, ChevronDown } from "lucide-react";
import { useState } from "react";
import { clsx } from "clsx";
import { count } from "@/lib/format";

export type FacetOption = { value: string; label?: string; count?: number; group?: string };

/** Searchable filter menu. Single or multiple choice, with live job counts. */
export function Facet({ label, options, selected, onChange, multiple, disabled, disabledHint }: {
  label: string; options: FacetOption[]; selected: string[]; onChange: (values: string[]) => void; multiple?: boolean; disabled?: boolean; disabledHint?: string;
}) {
  const [open, setOpen] = useState(false);
  const first = options.find((o) => o.value === selected[0]);
  const summary = selected.length === 0 ? label : selected.length === 1 ? first?.label ?? selected[0] : `${label}: ${selected.length}`;
  const groups = [...new Set(options.map((o) => o.group ?? ""))];

  const toggle = (value: string) => {
    if (multiple) onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);
    else { onChange(selected[0] === value ? [] : [value]); setOpen(false); }
  };

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button className="field inline-flex items-center gap-1.5 max-w-44 font-medium" data-active={selected.length > 0} disabled={disabled} title={disabled ? disabledHint : undefined}>
          <span className="truncate">{summary}</span>
          <ChevronDown size={14} aria-hidden className="shrink-0 opacity-70" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="start" sideOffset={4} className="z-50 w-72 bg-sheet rounded-md shadow-pop border border-line">
          <Command filter={(value, search) => (value.toLowerCase().includes(search.toLowerCase()) ? 1 : 0)}>
            <Command.Input placeholder={`Search ${label.toLowerCase()}`} className="w-full h-9 px-3 border-b border-line bg-transparent outline-none" />
            <Command.List className="max-h-72 overflow-y-auto p-1">
              <Command.Empty className="px-3 py-4 text-ink-2">Nothing matches that search.</Command.Empty>
              {groups.map((group) => (
                <Command.Group key={group} heading={group || undefined} className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:text-ink-3">
                  {options.filter((o) => (o.group ?? "") === group).map((o) => (
                    <Command.Item key={o.value} value={`${o.label ?? o.value} ${o.value}`} onSelect={() => toggle(o.value)}
                      className="flex items-center gap-2 px-2 h-8 rounded-[3px] cursor-pointer data-[selected=true]:bg-sheet-2">
                      <Check size={14} aria-hidden className={clsx("shrink-0 text-air-blue", !selected.includes(o.value) && "invisible")} />
                      <span className="truncate flex-1">{o.label ?? o.value}</span>
                      {o.count != null && <span className="tnum text-xs text-ink-3">{count(o.count)}</span>}
                    </Command.Item>
                  ))}
                </Command.Group>
              ))}
            </Command.List>
          </Command>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
