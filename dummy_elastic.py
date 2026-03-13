"""
dummy_elastic.py – Drop-in replacement for elastic.py for offline UI development.

Swap the import in app.py:
    from dummy_elastic import (search_food_items, add_food_item, get_metrics, seed_data_if_empty,
                                reserve_item, cancel_reservation, get_my_reservations,
                                get_available_qty, get_all_active_reservations)

All functions return data in exactly the same shape as the real elastic.py.
"""

import math
import uuid as _uuid
from datetime import datetime, timedelta, timezone

RESERVATION_MINUTES = 30


def _utcnow() -> datetime:
    """Timezone-naive UTC now (avoids deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── In-memory store ───────────────────────────────────────────────────────────

_now = _utcnow()

_STORE: list[dict] = [
    {
        "_item_id": "item-001",
        "title": "Butter Croissant Box (6 pcs)",
        "description": "Fresh unsold croissants from the evening batch. Perfectly flaky.",
        "merchant": "BakeHouse Tanjong Pagar",
        "price": 12.0, "discount_price": 5.0, "category": "Bakery",
        "quantity_available": 3,
        "location": {"lat": 1.2764, "lon": 103.8455},
        "pickup_end": (_now + timedelta(hours=3)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-002",
        "title": "Assorted Muffin Pack (4 pcs)",
        "description": "Blueberry and chocolate chip muffins baked this morning.",
        "merchant": "The Daily Grind Bugis",
        "price": 9.0, "discount_price": 4.0, "category": "Bakery",
        "quantity_available": 4,
        "location": {"lat": 1.3006, "lon": 103.8554},
        "pickup_end": (_now + timedelta(hours=2)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-003",
        "title": "Sushi Set (12 pcs)",
        "description": "End-of-day nigiri and maki — made fresh this afternoon.",
        "merchant": "Sakura Bento Raffles Place",
        "price": 22.0, "discount_price": 9.0, "category": "Japanese",
        "quantity_available": 2,
        "location": {"lat": 1.2834, "lon": 103.8516},
        "pickup_end": (_now + timedelta(hours=1, minutes=30)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-004",
        "title": "Chicken Pasta Box",
        "description": "Creamy carbonara with grilled chicken — full portion.",
        "merchant": "Pasta Republic Orchard",
        "price": 14.0, "discount_price": 6.0, "category": "Western",
        "quantity_available": 3,
        "location": {"lat": 1.3049, "lon": 103.8320},
        "pickup_end": (_now + timedelta(hours=2, minutes=45)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-005",
        "title": "Sandwich Wrap Combo",
        "description": "Tuna and egg mayo wraps with a bag of crisps.",
        "merchant": "Bites & Brews Dhoby Ghaut",
        "price": 10.0, "discount_price": 4.5, "category": "Cafe",
        "quantity_available": 5,
        "location": {"lat": 1.2990, "lon": 103.8455},
        "pickup_end": (_now + timedelta(hours=2)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-006",
        "title": "Char Siu Bao Set (5 pcs)",
        "description": "Steamed BBQ pork buns — end of lunch service.",
        "merchant": "Golden Palace Chinatown",
        "price": 8.0, "discount_price": 3.5, "category": "Asian",
        "quantity_available": 3,
        "location": {"lat": 1.2829, "lon": 103.8431},
        "pickup_end": (_now + timedelta(hours=1)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-007",
        "title": "Acai Bowl",
        "description": "Thick acai with granola and fresh fruit. Made an hour ago.",
        "merchant": "Bowls & Co Clarke Quay",
        "price": 13.0, "discount_price": 7.0, "category": "Cafe",
        "quantity_available": 2,
        "location": {"lat": 1.2896, "lon": 103.8461},
        "pickup_end": (_now + timedelta(hours=1, minutes=30)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-008",
        "title": "Poke Bowl (Large)",
        "description": "Salmon and tuna poke with edamame and sesame dressing.",
        "merchant": "Poke Theory City Hall",
        "price": 18.0, "discount_price": 8.0, "category": "Japanese",
        "quantity_available": 2,
        "location": {"lat": 1.2932, "lon": 103.8520},
        "pickup_end": (_now + timedelta(hours=2)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-009",
        "title": "Sourdough Loaf",
        "description": "Whole sourdough loaf baked this morning — half-price to clear.",
        "merchant": "Loafology Tiong Bahru",
        "price": 11.0, "discount_price": 5.5, "category": "Bakery",
        "quantity_available": 3,
        "location": {"lat": 1.2847, "lon": 103.8275},
        "pickup_end": (_now + timedelta(hours=4)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-010",
        "title": "Nasi Lemak Set",
        "description": "Coconut rice, sambal, egg, anchovies, and chicken wing.",
        "merchant": "Mamak Corner Lavender",
        "price": 8.0, "discount_price": 4.0, "category": "Asian",
        "quantity_available": 4,
        "location": {"lat": 1.3069, "lon": 103.8621},
        "pickup_end": (_now + timedelta(hours=1)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-011",
        "title": "Almond Croissant (3 pcs)",
        "description": "Twice-baked almond croissants — rich and nutty.",
        "merchant": "Maison Patisserie Orchard",
        "price": 14.0, "discount_price": 6.0, "category": "Bakery",
        "quantity_available": 3,
        "location": {"lat": 1.3069, "lon": 103.8318},
        "pickup_end": (_now + timedelta(hours=2)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-012",
        "title": "Teriyaki Chicken Bento",
        "description": "Grilled teriyaki chicken with Japanese rice and miso soup.",
        "merchant": "Bento Box Tanjong Pagar",
        "price": 16.0, "discount_price": 7.0, "category": "Japanese",
        "quantity_available": 2,
        "location": {"lat": 1.2764, "lon": 103.8440},
        "pickup_end": (_now + timedelta(hours=1, minutes=45)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-013",
        "title": "Fruit Tart Assortment (4 pcs)",
        "description": "Custard tarts topped with fresh seasonal fruit.",
        "merchant": "Sweet Endings Raffles Place",
        "price": 16.0, "discount_price": 7.0, "category": "Dessert",
        "quantity_available": 4,
        "location": {"lat": 1.2839, "lon": 103.8519},
        "pickup_end": (_now + timedelta(hours=2)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-014",
        "title": "Laksa Bowl",
        "description": "Rich coconut laksa broth with prawns and tofu puffs.",
        "merchant": "Spice Garden Bugis",
        "price": 10.0, "discount_price": 5.0, "category": "Asian",
        "quantity_available": 3,
        "location": {"lat": 1.3011, "lon": 103.8570},
        "pickup_end": (_now + timedelta(hours=1)).isoformat(),
        "listed_at": _now.isoformat(),
    },
    {
        "_item_id": "item-015",
        "title": "Cheese Danish (3 pcs)",
        "description": "Flaky pastry with cream cheese filling — morning bake.",
        "merchant": "Corner Bakery Marina Bay",
        "price": 11.0, "discount_price": 4.5, "category": "Bakery",
        "quantity_available": 4,
        "location": {"lat": 1.2816, "lon": 103.8565},
        "pickup_end": (_now + timedelta(hours=2, minutes=30)).isoformat(),
        "listed_at": _now.isoformat(),
    },
]

# ── Reservations store ────────────────────────────────────────────────────────
# { item_id: [{"session_id": str, "qty": int, "expires_at": datetime, ...}] }
_RESERVATIONS: dict[str, list] = {}


# ── Internal helpers ──────────────────────────────────────────────────────────

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


def _cleanup_expired():
    """Remove expired reservations from the in-memory store."""
    now = _utcnow()
    for item_id in list(_RESERVATIONS.keys()):
        _RESERVATIONS[item_id] = [
            r for r in _RESERVATIONS[item_id]
            if r["expires_at"] > now
        ]
        if not _RESERVATIONS[item_id]:
            del _RESERVATIONS[item_id]


def _get_reserved_qty(item_id: str) -> int:
    """Sum of active reservation quantities for an item (call after _cleanup_expired)."""
    return sum(r["qty"] for r in _RESERVATIONS.get(item_id, []))


# ── Public reservation API ────────────────────────────────────────────────────

def get_available_qty(item_id: str) -> int:
    """Returns how many units of item_id are currently not reserved."""
    _cleanup_expired()
    item = next((i for i in _STORE if i.get("_item_id") == item_id), None)
    if not item:
        return 0
    return max(0, item["quantity_available"] - _get_reserved_qty(item_id))


def reserve_item(item_id: str, qty: int, session_id: str) -> dict:
    """
    Reserve `qty` units of item_id for `session_id` for RESERVATION_MINUTES minutes.
    Returns {"success": bool, "message": str, "expires_at": datetime (on success)}.
    """
    _cleanup_expired()
    item = next((i for i in _STORE if i.get("_item_id") == item_id), None)
    if not item:
        return {"success": False, "message": "Item not found"}

    # Prevent double-reservation per session
    if any(r["session_id"] == session_id for r in _RESERVATIONS.get(item_id, [])):
        return {"success": False, "message": "You already have a reservation for this item"}

    available = item["quantity_available"] - _get_reserved_qty(item_id)
    if qty < 1 or qty > available:
        return {"success": False, "message": f"Only {available} unit(s) currently available"}

    expires_at = _utcnow() + timedelta(minutes=RESERVATION_MINUTES)
    reservation = {
        "session_id": session_id,
        "qty": qty,
        "expires_at": expires_at,
        "item_id": item_id,
        "item_title": item["title"],
        "merchant": item["merchant"],
        "discount_price": item["discount_price"],
        "reserved_at": _utcnow(),
    }
    _RESERVATIONS.setdefault(item_id, []).append(reservation)
    return {
        "success": True,
        "message": f"Reserved {qty} × {item['title']}",
        "expires_at": expires_at,
    }


def cancel_reservation(item_id: str, session_id: str) -> bool:
    """Cancel the session's reservation for item_id. Returns True if a reservation was cancelled."""
    if item_id not in _RESERVATIONS:
        return False
    original_len = len(_RESERVATIONS[item_id])
    _RESERVATIONS[item_id] = [r for r in _RESERVATIONS[item_id] if r["session_id"] != session_id]
    if not _RESERVATIONS[item_id]:
        del _RESERVATIONS[item_id]
    return len(_RESERVATIONS.get(item_id, [])) < original_len


def get_my_reservations(session_id: str) -> list:
    """
    Returns all active reservation dicts for this session.
    Each dict: item_id, item_title, merchant, qty, expires_at (datetime),
               discount_price, reserved_at (datetime).
    """
    _cleanup_expired()
    result = []
    for item_id, reservations in _RESERVATIONS.items():
        for r in reservations:
            if r["session_id"] == session_id:
                result.append(r)
    return result


def get_all_active_reservations() -> dict:
    """Returns {item_id: total_reserved_qty} for all items with active reservations."""
    _cleanup_expired()
    return {item_id: _get_reserved_qty(item_id) for item_id in _RESERVATIONS}


# ── Public API (same signatures as elastic.py) ────────────────────────────────

def seed_data_if_empty():
    """No-op for the dummy backend — data is already in memory."""
    pass


def search_food_items(keyword: str, lat: float, lon: float, radius_km: int = 2) -> list:
    """
    Returns a list of ES-style hit dicts:
        [{"_id": str, "_source": {...}, "sort": [distance_metres]}, ...]
    Filters by radius, non-expired pickup, and keyword; sorted closest-first.
    """
    _cleanup_expired()
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

        item_id = item.get("_item_id", "")
        hits.append({
            "_id": item_id,
            "_source": item,
            "sort": [dist_m],
        })

    hits.sort(key=lambda h: h["sort"][0])
    return hits[:20]


def add_food_item(doc: dict) -> bool:
    """Appends a new listing to the in-memory store."""
    doc = dict(doc)
    doc["_item_id"] = str(_uuid.uuid4())
    if "quantity_available" not in doc:
        doc["quantity_available"] = 1
    _STORE.append(doc)
    return True


def get_metrics() -> dict:
    """Returns the same metric dict shape as the real elastic.py, plus reservation stats."""
    _cleanup_expired()
    now = _utcnow()
    active = [
        item for item in _STORE
        if datetime.fromisoformat(item["pickup_end"]) >= now
    ]

    total_saving = sum(i["price"] - i["discount_price"] for i in active)
    avg_saving = total_saving / len(active) if active else 0.0
    total_qty = sum(i.get("quantity_available", 1) for i in active)
    total_reserved = sum(_get_reserved_qty(i.get("_item_id", "")) for i in active)

    by_category: dict[str, int] = {}
    for item in active:
        cat = item.get("category", "Other")
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "total_items":    len(active),
        "total_saving":   total_saving,
        "avg_saving":     avg_saving,
        "by_category":    by_category,
        "total_qty":      total_qty,
        "total_reserved": total_reserved,
    }
