"""Location resolver backed by GeoNames. Turns 'Bengaluru' or 'Bangalore, KA' into one city, state and country."""
import csv
import io
import re
import zipfile
from dataclasses import dataclass
from functools import lru_cache

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import GeoCountry, GeoName, GeoPlace
from .text import fold, norm_key

csv.field_size_limit(10_000_000)
BASE = "https://download.geonames.org/export/dump/"

# Countries whose names or aliases appear in postings but are not in GeoNames' country list as such.
COUNTRY_ALIASES = {
    "usa": "US", "us": "US", "u s a": "US", "u s": "US", "united states of america": "US", "america": "US",
    "uk": "GB", "u k": "GB", "great britain": "GB", "britain": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "northern ireland": "GB", "uae": "AE", "emirates": "AE", "south korea": "KR", "korea": "KR", "czech republic": "CZ",
    "czechia": "CZ", "holland": "NL", "the netherlands": "NL", "deutschland": "DE", "espana": "ES", "brasil": "BR",
    "netherlands": "NL", "nederland": "NL", "italia": "IT", "osterreich": "AT", "schweiz": "CH", "suisse": "CH", "polska": "PL",
    "republic of ireland": "IE", "aotearoa": "NZ", "russia": "RU", "turkey": "TR", "turkiye": "TR", "vietnam": "VN",
}
REMOTE_WORDS = re.compile(r"\b(remote|work from home|wfh|anywhere|worldwide|global|distributed|homeoffice|home office|telecommute)\b", re.I)
HYBRID_WORDS = re.compile(r"\bhybrid\b", re.I)
# Words to remove before looking up a place.
NOISE = re.compile(r"\b(remote|hybrid|on-?site|onsite|in-office|offices?|anywhere( in the world)?|any location|distributed|homeoffice|work from home|wfh|only|based|time zones?|hq|headquarters?|headquater|metro(politan)?( area)?|greater|area|region|district)\b", re.I)
CITY_STATES = {"SG", "HK", "MO", "MC"}  # the country name is also the city
REGION_ONLY = {"europe", "emea", "eu", "european union", "apac", "asia", "latam", "latin america", "north america",
               "americas", "africa", "middle east", "oceania", "worldwide", "global", "anywhere", "asia pacific"}


@dataclass
class Place:
    country_code: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    lat: float | None = None
    lng: float | None = None


def _download(name: str) -> bytes:
    cache = get_settings().data_dir / "geonames"
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / name
    if not path.exists():
        with httpx.stream("GET", BASE + name, timeout=300, follow_redirects=True) as response:
            response.raise_for_status()
            with path.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
    return path.read_bytes()


def load_geonames(db: Session) -> int:
    """Load countries, first-level regions and every place over 1,000 people. Safe to re-run."""
    countries: list[dict] = []
    for line in _download("countryInfo.txt").decode("utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        f = line.split("\t")
        countries.append({"code": f[0], "name": f[4], "continent": f[8], "currency": f[10] or None})
    db.execute(text("TRUNCATE geo_countries, geo_names, geo_places CASCADE"))
    db.execute(GeoCountry.__table__.insert(), countries)

    admin1: dict[str, str] = {}
    for line in _download("admin1CodesASCII.txt").decode("utf-8").splitlines():
        f = line.split("\t")
        admin1[f[0]] = f[1]

    with zipfile.ZipFile(io.BytesIO(_download("cities1000.zip"))) as archive:
        raw = archive.read("cities1000.txt").decode("utf-8")

    places: list[dict] = []
    names: dict[tuple[str, int], None] = {}
    count = 0
    for f in csv.reader(io.StringIO(raw), delimiter="\t", quoting=csv.QUOTE_NONE):
        place_id = int(f[0])
        code = f[8]
        places.append({
            "id": place_id, "name": f[1], "country_code": code, "admin1": admin1.get(f"{code}.{f[10]}"),
            "admin1_code": f[10] or None, "lat": float(f[4]), "lng": float(f[5]), "population": int(f[14] or 0),
        })
        for candidate in [f[1], f[2], *f[3].split(",")]:
            key = norm_key(candidate)  # non-Latin spellings normalise to empty and are skipped
            if key and len(key) <= 120:
                names[(key, place_id)] = None
        count += 1
        if len(places) >= 5000:
            db.execute(GeoPlace.__table__.insert(), places)
            places.clear()
    if places:
        db.execute(GeoPlace.__table__.insert(), places)
    batch = [{"norm": k, "place_id": p} for k, p in names]
    for start in range(0, len(batch), 10000):
        db.execute(GeoName.__table__.insert(), batch[start:start + 10000])
    db.commit()
    resolver_tables.cache_clear()
    return count


@lru_cache
def resolver_tables() -> tuple[dict[str, str], dict[str, str], dict[str, dict[str, str]]]:
    """(country key -> code, code -> name, code -> {region key -> region name})."""
    from ..db import SessionLocal

    with SessionLocal() as db:
        keys = dict(COUNTRY_ALIASES)
        names: dict[str, str] = {}
        for row in db.execute(select(GeoCountry.code, GeoCountry.name)):
            names[row.code] = row.name
            keys[norm_key(row.name)] = row.code
        regions: dict[str, dict[str, str]] = {}
        for row in db.execute(select(GeoPlace.country_code, GeoPlace.admin1, GeoPlace.admin1_code).distinct()):
            if row.admin1:
                bucket = regions.setdefault(row.country_code, {})
                bucket[norm_key(row.admin1)] = row.admin1
                # "NSW", "CA", "KA": GeoNames codes are postal codes for some countries only.
                if row.admin1_code and row.admin1_code.isalpha():
                    bucket[row.admin1_code.lower()] = row.admin1
        for code, abbrevs in REGION_ABBREVIATIONS.items():
            bucket = regions.setdefault(code, {})
            for short, full in abbrevs.items():
                match = bucket.get(norm_key(full))
                if match:
                    bucket[short] = match
    return keys, names, regions


REGION_ABBREVIATIONS = {
    "AU": {"nsw": "New South Wales", "vic": "Victoria", "qld": "Queensland", "wa": "Western Australia", "sa": "South Australia",
           "tas": "Tasmania", "act": "Australian Capital Territory", "nt": "Northern Territory"},
    "IN": {"ka": "Karnataka", "mh": "Maharashtra", "tn": "Tamil Nadu", "dl": "Delhi", "ts": "Telangana", "tg": "Telangana",
           "ap": "Andhra Pradesh", "up": "Uttar Pradesh", "wb": "West Bengal", "gj": "Gujarat", "hr": "Haryana", "kl": "Kerala",
           "rj": "Rajasthan", "pb": "Punjab", "br": "Bihar", "mp": "Madhya Pradesh", "or": "Odisha"},
    "CA": {"on": "Ontario", "bc": "British Columbia", "qc": "Quebec", "ab": "Alberta", "mb": "Manitoba", "sk": "Saskatchewan",
           "ns": "Nova Scotia", "nb": "New Brunswick", "nl": "Newfoundland and Labrador", "pe": "Prince Edward Island"},
}


class Resolver:
    """Per-run resolver. Caches by input string, so repeated locations cost one query."""

    def __init__(self, db: Session):
        self.db = db
        self.keys, self.names, self.regions = resolver_tables()
        self.cache: dict[tuple[str, str | None], Place] = {}

    def _country(self, key: str) -> str | None:
        return self.keys.get(key)

    def _best_place(self, key: str, country: str | None, region: str | None) -> GeoPlace | None:
        stmt = select(GeoPlace).join(GeoName, GeoName.place_id == GeoPlace.id).where(GeoName.norm == key)
        if country:
            stmt = stmt.where(GeoPlace.country_code == country)
        if region:
            stmt = stmt.where(GeoPlace.admin1 == region)
        return self.db.scalars(stmt.order_by(GeoPlace.population.desc()).limit(1)).first()

    def resolve(self, raw: str | None, hint_country: str | None = None) -> Place:
        cache_key = (raw or "", hint_country)
        if cache_key not in self.cache:
            self.cache[cache_key] = self._resolve(raw, hint_country)
        return self.cache[cache_key]

    def _resolve(self, raw: str | None, hint_country: str | None) -> Place:
        place = Place(country_code=hint_country, country=self.names.get(hint_country or ""))
        if not raw:
            return place
        # Handle "Sydney, NSW | Melbourne, VIC" and "Poland OR Romania" by using the first location listed.
        first = re.split(r"[|;/•\n]|\s(?:or|and)\s", raw, flags=re.I)[0]
        country = hint_country
        # "Remote (US)": a country in brackets is information, anything else in brackets is noise.
        for bracketed in re.findall(r"\((.*?)\)", first):
            code = self._country(norm_key(bracketed)) or ("US" if bracketed.strip() == "US" else None)
            country = country or code
        cleaned = NOISE.sub(" ", re.sub(r"\(.*?\)", " ", first))
        cleaned = re.sub(r"\b\d{3,}\b", " ", cleaned)  # postcodes
        parts = [re.sub(r"^(in|all|the)\s+", "", norm_key(p)) for p in re.split(r",|\s[-–—]\s", cleaned)]
        parts = [p for p in parts if p and p not in REGION_ONLY]
        if not parts:
            return Place(country_code=country, country=self.names.get(country or ""))

        # "United Kingdom - London": the country can come first.
        if len(parts) > 1 and self._country(parts[0]) and not self._country(parts[-1]):
            country = self._country(parts[0])
            parts = parts[1:]
        if parts and self._country(parts[-1]):
            # "CA" is both Canada and California: with a preceding part, prefer a US state reading.
            is_us_state = len(parts) > 1 and parts[-1] in self.regions.get("US", {}) and len(parts[-1]) == 2
            if not is_us_state or hint_country not in (None, "US"):
                if not is_us_state:
                    country = self._country(parts[-1])
                    parts = parts[:-1]
        if not parts:
            if country in CITY_STATES:
                match = self._best_place(norm_key(self.names[country]), country, None)
                if match:
                    return Place(country, self.names[country], match.admin1, match.name, match.lat, match.lng)
            return Place(country_code=country, country=self.names.get(country or ""))

        region: str | None = None
        if len(parts) >= 2:
            tail = parts[-1]
            if country and tail in self.regions.get(country, {}):
                region = self.regions[country][tail]
                parts = parts[:-1]
            elif not country and len(tail) == 2 and tail in self.regions.get("US", {}):
                country, region = "US", self.regions["US"][tail]
                parts = parts[:-1]
            elif not country:
                for code, bucket in self.regions.items():
                    if tail in bucket and len(tail) > 3:
                        country, region = code, bucket[tail]
                        parts = parts[:-1]
                        break

        city_key = parts[0]
        # A lone region name: "Queensland", "Karnataka".
        if len(parts) == 1 and country and city_key in self.regions.get(country, {}) and region is None:
            match = self._best_place(city_key, country, None)
            if match is None or match.population < 50_000:
                return Place(country_code=country, country=self.names.get(country), state=self.regions[country][city_key])

        match = self._best_place(city_key, country, region) or (self._best_place(city_key, country, None) if region else None)
        # "9th arrondissement, Paris": the city may not be the first part.
        for later in parts[1:]:
            match = match or self._best_place(later, country, region)
        if match:
            return Place(match.country_code, self.names.get(match.country_code), match.admin1 or region, match.name, match.lat, match.lng)
        if country and self._country(city_key) == country:
            return Place(country_code=country, country=self.names.get(country), state=region)
        return Place(country_code=country, country=self.names.get(country or ""), state=region)


def infer_workplace(location: str | None, title: str | None, flag: bool | None = None) -> str:
    if flag:
        return "remote"
    text_value = f"{location or ''} {title or ''}"
    if HYBRID_WORDS.search(text_value):
        return "hybrid"
    if REMOTE_WORDS.search(text_value):
        return "remote"
    return "onsite" if location else "unknown"


__all__ = ["Place", "Resolver", "load_geonames", "infer_workplace", "fold"]
