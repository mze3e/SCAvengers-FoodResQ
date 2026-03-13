"""
dummy_elastic.py – Drop-in replacement for elastic.py for offline UI development.

Swap the import in app.py:
    from dummy_elastic import (search_food_items, add_food_item, get_metrics, seed_data_if_empty)

All four functions return data in exactly the same shape as the real elastic.py.
"""

import math
from datetime import datetime, timedelta, timezone


def _utcnow() -> datetime:
    """Timezone-naive UTC now (avoids deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ── In-memory store ───────────────────────────────────────────────────────────

_now = _utcnow()

_STORE: list[dict] = [
    {
        "title": "Butter Croissant Box (6 pcs)",
        "description": "Fresh unsold croissants from the evening batch. Perfectly flaky.",
        "merchant": "BakeHouse Tanjong Pagar",
        "price": 12.0, "discount_price": 5.0, "category": "Bakery",
        "location": {"lat": 1.2764, "lon": 103.8455},
        "pickup_end": (_now + timedelta(hours=3)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Assorted Muffin Pack (4 pcs)",
        "description": "Blueberry and chocolate chip muffins baked this morning.",
        "merchant": "The Daily Grind Bugis",
        "price": 9.0, "discount_price": 4.0, "category": "Bakery",
        "location": {"lat": 1.3006, "lon": 103.8554},
        "pickup_end": (_now + timedelta(hours=2)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Sushi Set (12 pcs)",
        "description": "End-of-day nigiri and maki — made fresh this afternoon.",
        "merchant": "Sakura Bento Raffles Place",
        "price": 22.0, "discount_price": 9.0, "category": "Japanese",
        "location": {"lat": 1.2834, "lon": 103.8516},
        "pickup_end": (_now + timedelta(hours=1, minutes=30)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Chicken Pasta Box",
        "description": "Creamy carbonara with grilled chicken — full portion.",
        "merchant": "Pasta Republic Orchard",
        "price": 14.0, "discount_price": 6.0, "category": "Western",
        "location": {"lat": 1.3049, "lon": 103.8320},
        "pickup_end": (_now + timedelta(hours=2, minutes=45)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Sandwich Wrap Combo",
        "description": "Tuna and egg mayo wraps with a bag of crisps.",
        "merchant": "Bites & Brews Dhoby Ghaut",
        "price": 10.0, "discount_price": 4.5, "category": "Cafe",
        "location": {"lat": 1.2990, "lon": 103.8455},
        "pickup_end": (_now + timedelta(hours=2)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Char Siu Bao Set (5 pcs)",
        "description": "Steamed BBQ pork buns — end of lunch service.",
        "merchant": "Golden Palace Chinatown",
        "price": 8.0, "discount_price": 3.5, "category": "Asian",
        "location": {"lat": 1.2829, "lon": 103.8431},
        "pickup_end": (_now + timedelta(hours=1)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Acai Bowl",
        "description": "Thick acai with granola and fresh fruit. Made an hour ago.",
        "merchant": "Bowls & Co Clarke Quay",
        "price": 13.0, "discount_price": 7.0, "category": "Cafe",
        "location": {"lat": 1.2896, "lon": 103.8461},
        "pickup_end": (_now + timedelta(hours=1, minutes=30)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Poke Bowl (Large)",
        "description": "Salmon and tuna poke with edamame and sesame dressing.",
        "merchant": "Poke Theory City Hall",
        "price": 18.0, "discount_price": 8.0, "category": "Japanese",
        "location": {"lat": 1.2932, "lon": 103.8520},
        "pickup_end": (_now + timedelta(hours=2)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Sourdough Loaf",
        "description": "Whole sourdough loaf baked this morning — half-price to clear.",
        "merchant": "Loafology Tiong Bahru",
        "price": 11.0, "discount_price": 5.5, "category": "Bakery",
        "location": {"lat": 1.2847, "lon": 103.8275},
        "pickup_end": (_now + timedelta(hours=4)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Nasi Lemak Set",
        "description": "Coconut rice, sambal, egg, anchovies, and chicken wing.",
        "merchant": "Mamak Corner Lavender",
        "price": 8.0, "discount_price": 4.0, "category": "Asian",
        "location": {"lat": 1.3069, "lon": 103.8621},
        "pickup_end": (_now + timedelta(hours=1)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Almond Croissant (3 pcs)",
        "description": "Twice-baked almond croissants — rich and nutty.",
        "merchant": "Maison Patisserie Orchard",
        "price": 14.0, "discount_price": 6.0, "category": "Bakery",
        "location": {"lat": 1.3069, "lon": 103.8318},
        "pickup_end": (_now + timedelta(hours=2)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Teriyaki Chicken Bento",
        "description": "Grilled teriyaki chicken with Japanese rice and miso soup.",
        "merchant": "Bento Box Tanjong Pagar",
        "price": 16.0, "discount_price": 7.0, "category": "Japanese",
        "location": {"lat": 1.2764, "lon": 103.8440},
        "pickup_end": (_now + timedelta(hours=1, minutes=45)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Fruit Tart Assortment (4 pcs)",
        "description": "Custard tarts topped with fresh seasonal fruit.",
        "merchant": "Sweet Endings Raffles Place",
        "price": 16.0, "discount_price": 7.0, "category": "Dessert",
        "location": {"lat": 1.2839, "lon": 103.8519},
        "pickup_end": (_now + timedelta(hours=2)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Laksa Bowl",
        "description": "Rich coconut laksa broth with prawns and tofu puffs.",
        "merchant": "Spice Garden Bugis",
        "price": 10.0, "discount_price": 5.0, "category": "Asian",
        "location": {"lat": 1.3011, "lon": 103.8570},
        "pickup_end": (_now + timedelta(hours=1)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "title": "Cheese Danish (3 pcs)",
        "description": "Flaky pastry with cream cheese filling — morning bake.",
        "merchant": "Corner Bakery Marina Bay",
        "price": 11.0, "discount_price": 4.5, "category": "Bakery",
        "location": {"lat": 1.2816, "lon": 103.8565},
        "pickup_end": (_now + timedelta(hours=2, minutes=30)).isoformat(),
        "listed_at": _now.isoformat(),
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Returns distance in metres between two lat/lon points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _matches_keyword(item: dict, keyword: str) -> bool:
    kw = keyword.strip().lower()
    if not kw:
        return True
    haystack = " ".join([
        item.get("title", ""),
        item.get("description", ""),
        item.get("merchant", ""),
        item.get("category", ""),
    ]).lower()
    return kw in haystack


# ── Public API (same signatures as elastic.py) ────────────────────────────────

def seed_data_if_empty():
    """No-op for the dummy backend — data is already in memory."""
    pass


def search_food_items(keyword: str, lat: float, lon: float, radius_km: int = 2) -> list:
    """
    Returns a list of ES-style hit dicts:
        [{"_source": {...}, "sort": [distance_metres]}, ...]
    Filters by radius, non-expired pickup, and keyword; sorted closest-first.
    """
    now = _utcnow()
    radius_m = radius_km * 1000
    hits = []

    for item in _STORE:
        # Expiry filter
        try:
            if datetime.fromisoformat(item["pickup_end"]) < now:
                continue
        except Exception:
            pass

        # Geo filter
        loc = item["location"]
        dist_m = _haversine_m(lat, lon, loc["lat"], loc["lon"])
        if dist_m > radius_m:
            continue

        # Keyword filter
        if not _matches_keyword(item, keyword):
            continue

        hits.append({"_source": item, "sort": [dist_m]})

    hits.sort(key=lambda h: h["sort"][0])
    return hits[:20]


def add_food_item(doc: dict) -> bool:
    """Appends a new listing to the in-memory store."""
    _STORE.append(doc)
    return True


def get_metrics() -> dict:
    """Returns the same metric dict shape as the real elastic.py."""
    now = _utcnow()
    active = [
        item for item in _STORE
        if datetime.fromisoformat(item["pickup_end"]) >= now
    ]

    total_saving = sum(i["price"] - i["discount_price"] for i in active)
    avg_saving = total_saving / len(active) if active else 0.0

    by_category: dict[str, int] = {}
    for item in active:
        cat = item.get("category", "Other")
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "total_items":  len(active),
        "total_saving": total_saving,
        "avg_saving":   avg_saving,
        "by_category":  by_category,
    }
