"""Deterministic skill extraction from a curated taxonomy (data/taxonomy/skills.txt)."""
import re
from dataclasses import dataclass
from functools import lru_cache

from ..config import get_settings

# Single-letter or everyday-word skills only count when written with exactly this capitalisation.
CASE_SENSITIVE = {"R", "Go", "Rust", "Swift", "Spring", "Express", "Git", "Agile", "SOC", "SAS", "QA", "RAG", "Lambda",
                  "Spark", "Hive", "Helm", "Dart", "Flask", "Excel", "Node.js", "Looker", "ROS", "SAP"}
# Extra guard: these need context, because they are common English words or abbreviations.
AMBIGUOUS_ALIASES = {"ml", "js", "ts", "node", "elt", "pcb", "plc"}


@dataclass(frozen=True)
class SkillDef:
    name: str
    category: str
    pattern: re.Pattern


def _compile(term: str, case_sensitive: bool) -> str:
    escaped = re.escape(term).replace(r"\ ", r"[\s-]")
    return rf"(?<![\w+#.]){escaped}(?![\w+#]|\.[a-zA-Z])"


@lru_cache
def load_taxonomy() -> tuple[SkillDef, ...]:
    path = get_settings().data_dir / "taxonomy" / "skills.txt"
    skills: list[SkillDef] = []
    category = "Other"
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            category = line[1:-1]
            continue
        name, _, alias_text = line.partition("=")
        name = name.strip()
        aliases = [a.strip() for a in alias_text.split(",") if a.strip()]
        case_sensitive = name in CASE_SENSITIVE or len(name) <= 2
        parts = [_compile(name, case_sensitive)]
        # Aliases are distinctive spellings, so they match in any case unless known to be ambiguous.
        alias_parts = [_compile(a, False) for a in aliases if a.lower() not in AMBIGUOUS_ALIASES]
        strict_parts = [_compile(a.upper() if a.lower() in {"ml", "pcb", "plc", "elt"} else a, True)
                        for a in aliases if a.lower() in AMBIGUOUS_ALIASES]
        if case_sensitive:
            body = "|".join(parts + strict_parts)
            if alias_parts:
                body = f"{body}|(?i:{'|'.join(alias_parts)})"
        else:
            body = f"(?i:{'|'.join(parts + alias_parts)})"
            if strict_parts:
                body = f"{body}|{'|'.join(strict_parts)}"
        skills.append(SkillDef(name=name, category=category, pattern=re.compile(body)))
    return tuple(skills)


def extract_skills(text: str) -> list[str]:
    if not text:
        return []
    text = text[:30000]
    return [s.name for s in load_taxonomy() if s.pattern.search(text)]
