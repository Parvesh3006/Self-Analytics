"""Runs against the loaded GeoNames tables in the local database."""
import pytest

from app.db import SessionLocal
from app.normalize.geo import Resolver, infer_workplace


@pytest.fixture(scope="module")
def resolver():
    db = SessionLocal()
    yield Resolver(db)
    db.close()


@pytest.mark.parametrize("raw,hint,country,state,city", [
    ("Bengaluru", None, "IN", "Karnataka", "Bengaluru"),
    ("Bangalore, KA", "IN", "IN", "Karnataka", "Bengaluru"),
    ("Sydney, NSW", "AU", "AU", "New South Wales", "Sydney"),
    ("Sydney, Australia", None, "AU", "New South Wales", "Sydney"),
    ("San Francisco, CA", None, "US", "California", "San Francisco"),
    ("Toronto, Ontario, Canada", None, "CA", "Ontario", "Toronto"),
    ("London, UK", None, "GB", "England", "London"),
    ("Dublin, Ireland", None, "IE", "Leinster", "Dublin"),
    ("Auckland, New Zealand", None, "NZ", "Auckland", "Auckland"),
    ("Singapore", None, "SG", None, "Singapore"),
    ("München, Germany", None, "DE", "Bavaria", "Munich"),
    ("United Kingdom - London", None, "GB", None, "London"),
    ("Sydney Or Melbourne", "AU", "AU", "New South Wales", "Sydney"),
    ("9th arrondissement, Paris, France", None, "FR", None, "Paris"),
    ("Paris offices", "FR", "FR", None, "Paris"),
])
def test_places(resolver, raw, hint, country, state, city):
    place = resolver.resolve(raw, hint)
    assert place.country_code == country
    assert place.city == city
    if state:
        assert place.state == state


@pytest.mark.parametrize("raw", ["Remote", "Worldwide", "Anywhere", "EMEA", ""])
def test_no_false_places(resolver, raw):
    place = resolver.resolve(raw)
    assert place.country_code is None and place.city is None


@pytest.mark.parametrize("raw,code", [("Remote - Canada", "CA"), ("Netherlands", "NL"), ("Remote (US)", "US"), ("Remote in Germany", "DE"), ("All France (remote)", "FR")])
def test_country_only(resolver, raw, code):
    place = resolver.resolve(raw)
    assert place.country_code == code and place.city is None


def test_workplace():
    assert infer_workplace("Remote, USA", "Engineer") == "remote"
    assert infer_workplace("Berlin (Hybrid)", "Engineer") == "hybrid"
    assert infer_workplace("Berlin", "Engineer") == "onsite"
    assert infer_workplace(None, "Engineer") == "unknown"
