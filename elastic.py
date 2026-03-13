"""
elastic.py – All OpenSearch interactions for FoodResQ.
Uses AWS IAM request signing via boto3 + requests-aws4auth.
"""

import os
import boto3
from datetime import datetime, timedelta, timezone
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

INDEX = "food_items"
RESERVATIONS_INDEX = "food_reservations"
REGION = os.getenv("AWS_REGION", "us-west-2")
_raw_url = os.getenv("ES_URL", "")
HOST = _raw_url.replace("https://", "").replace("http://", "").rstrip("/")
RESERVATION_MINUTES = 30

# ── Client ────────────────────────────────────────────────────────────────────

def get_client() -> OpenSearch:
    """
    Returns an OpenSearch client authenticated via AWS IAM signing.
    On Elastic Beanstalk the EC2 instance role supplies credentials
    automatically via the instance metadata service — no keys needed in code.
    """
    if not HOST:
        raise ValueError("ES_URL is not set. Add it to the EB environment properties.")

    session = boto3.Session()
    credentials = session.get_credentials().get_frozen_credentials()
    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        REGION,
        "es",
        session_token=credentials.token,
    )
    return OpenSearch(
        hosts=[{"host": HOST, "port": 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )


# ── Index setup ───────────────────────────────────────────────────────────────

def ensure_index(es: OpenSearch):
    """Creates the food_items index with geo_point mapping if it doesn't exist."""
    if es.indices.exists(index=INDEX):
        return

    mapping = {
        "mappings": {
            "properties": {
                "title":              {"type": "text"},
                "description":        {"type": "text"},
                "merchant":           {"type": "keyword"},
                "price":              {"type": "float"},
                "discount_price":     {"type": "float"},
                "category":           {"type": "keyword"},
                "location":           {"type": "geo_point"},
                "pickup_end":         {"type": "date"},
                "listed_at":          {"type": "date"},
                "quantity_available": {"type": "integer"},
            }
        }
    }
    es.indices.create(index=INDEX, body=mapping)


def ensure_reservations_index(es: OpenSearch):
    """Creates the food_reservations index if it doesn't exist."""
    if es.indices.exists(index=RESERVATIONS_INDEX):
        return

    mapping = {
        "mappings": {
            "properties": {
                "item_id":        {"type": "keyword"},
                "session_id":     {"type": "keyword"},
                "qty":            {"type": "integer"},
                "expires_at":     {"type": "date"},
                "item_title":     {"type": "text"},
                "merchant":       {"type": "keyword"},
                "discount_price": {"type": "float"},
                "category":       {"type": "keyword"},
                "location":       {"type": "geo_point"},
                "pickup_end":     {"type": "date"},
                "listed_at":      {"type": "date"},
                "reserved_at":    {"type": "date"},
            }
        }
    }
    es.indices.create(index=RESERVATIONS_INDEX, body=mapping)


# ── Search ────────────────────────────────────────────────────────────────────

def search_food_items(keyword: str, lat: float, lon: float, radius_km: int = 2) -> list:
    """
    Full-text keyword search filtered by geo distance.
    Results sorted by distance (closest first).
    """
    es = get_client()
    ensure_index(es)

    must_clause = (
        {"multi_match": {"query": keyword, "fields": ["title^2", "description", "merchant", "category"]}}
        if keyword.strip()
        else {"match_all": {}}
    )

    query = {
        "query": {
            "bool": {
                "must": must_clause,
                "filter": [
                    {
                        "geo_distance": {
                            "distance": f"{radius_km}km",
                            "location": {"lat": lat, "lon": lon},
                        }
                    },
                    {
                        "range": {
                            "pickup_end": {"gte": "now"}
                        }
                    },
                ],
            }
        },
        "sort": [
            {
                "_geo_distance": {
                    "location": {"lat": lat, "lon": lon},
                    "order": "asc",
                    "unit": "m",
                }
            }
        ],
        "size": 20,
    }

    response = es.search(index=INDEX, body=query)
    return response["hits"]["hits"]


# ── Index a document ──────────────────────────────────────────────────────────

def add_food_item(doc: dict) -> bool:
    """Indexes a new food listing. Returns True on success."""
    try:
        es = get_client()
        ensure_index(es)
        if "quantity_available" not in doc:
            doc["quantity_available"] = 1
        es.index(index=INDEX, document=doc)
        return True
    except Exception as e:
        print(f"[FoodResQ] Error indexing item: {e}")
        return False


# ── Reservation functions ─────────────────────────────────────────────────────

def get_available_qty(item_id: str) -> int:
    """Returns how many units of item_id are not currently reserved."""
    try:
        es = get_client()
        ensure_index(es)
        ensure_reservations_index(es)

        item_res = es.get(index=INDEX, id=item_id, ignore=[404])
        if not item_res.get("found"):
            return 0
        total_qty = item_res["_source"].get("quantity_available", 1)

        res = es.search(index=RESERVATIONS_INDEX, body={
            "query": {
                "bool": {
                    "must": [
                        {"term": {"item_id": item_id}},
                        {"range": {"expires_at": {"gte": "now"}}},
                    ]
                }
            },
            "aggs": {"reserved": {"sum": {"field": "qty"}}},
            "size": 0,
        })
        reserved = int(res["aggregations"]["reserved"]["value"] or 0)
        return max(0, total_qty - reserved)
    except Exception as e:
        print(f"[FoodResQ] Error getting available qty: {e}")
        return 0


def reserve_item(item_id: str, qty: int, session_id: str) -> dict:
    """
    Reserve `qty` units for `session_id` for RESERVATION_MINUTES minutes.
    Returns {"success": bool, "message": str, "expires_at": datetime (on success)}.
    """
    try:
        es = get_client()
        ensure_reservations_index(es)

        # Check for existing active reservation
        existing = es.search(index=RESERVATIONS_INDEX, body={
            "query": {
                "bool": {
                    "must": [
                        {"term": {"item_id": item_id}},
                        {"term": {"session_id": session_id}},
                        {"range": {"expires_at": {"gte": "now"}}},
                    ]
                }
            }
        })
        if existing["hits"]["total"]["value"] > 0:
            return {"success": False, "message": "You already have a reservation for this item"}

        available = get_available_qty(item_id)
        if qty < 1 or qty > available:
            return {"success": False, "message": f"Only {available} unit(s) currently available"}

        item_res = es.get(index=INDEX, id=item_id, ignore=[404])
        item = item_res.get("_source", {})

        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(minutes=RESERVATION_MINUTES)

        es.index(index=RESERVATIONS_INDEX, document={
            "item_id":        item_id,
            "session_id":     session_id,
            "qty":            qty,
            "expires_at":     expires_at.isoformat(),
            "item_title":     item.get("title", ""),
            "merchant":       item.get("merchant", ""),
            "discount_price": item.get("discount_price", 0),
            "reserved_at":    now_utc.isoformat(),
        })

        expires_naive = expires_at.replace(tzinfo=None)
        return {
            "success":    True,
            "message":    f"Reserved {qty} × {item.get('title', '')}",
            "expires_at": expires_naive,
        }
    except Exception as e:
        print(f"[FoodResQ] Error reserving item: {e}")
        return {"success": False, "message": str(e)}


def cancel_reservation(item_id: str, session_id: str) -> bool:
    """Cancel the session's reservation for item_id."""
    try:
        es = get_client()
        ensure_reservations_index(es)
        res = es.delete_by_query(index=RESERVATIONS_INDEX, body={
            "query": {
                "bool": {
                    "must": [
                        {"term": {"item_id": item_id}},
                        {"term": {"session_id": session_id}},
                    ]
                }
            }
        })
        return res["deleted"] > 0
    except Exception as e:
        print(f"[FoodResQ] Error cancelling reservation: {e}")
        return False


def get_my_reservations(session_id: str) -> list:
    """Returns all active reservation dicts for this session."""
    try:
        es = get_client()
        ensure_reservations_index(es)
        res = es.search(index=RESERVATIONS_INDEX, body={
            "query": {
                "bool": {
                    "must": [
                        {"term": {"session_id": session_id}},
                        {"range": {"expires_at": {"gte": "now"}}},
                    ]
                }
            },
            "size": 20,
        })
        reservations = []
        for hit in res["hits"]["hits"]:
            r = hit["_source"]
            try:
                expires_at = datetime.fromisoformat(
                    r.get("expires_at", "").replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except Exception:
                expires_at = datetime.utcnow()
            reservations.append({
                "item_id":        r.get("item_id", ""),
                "item_title":     r.get("item_title", ""),
                "merchant":       r.get("merchant", ""),
                "qty":            r.get("qty", 1),
                "expires_at":     expires_at,
                "discount_price": r.get("discount_price", 0),
                "reserved_at":    r.get("reserved_at", ""),
            })
        return reservations
    except Exception as e:
        print(f"[FoodResQ] Error fetching reservations: {e}")
        return []


def get_all_active_reservations() -> dict:
    """Returns {item_id: total_reserved_qty} for the Impact dashboard."""
    try:
        es = get_client()
        ensure_reservations_index(es)
        res = es.search(index=RESERVATIONS_INDEX, body={
            "query": {"range": {"expires_at": {"gte": "now"}}},
            "aggs": {
                "by_item": {
                    "terms": {"field": "item_id", "size": 100},
                    "aggs": {"total_qty": {"sum": {"field": "qty"}}},
                }
            },
            "size": 0,
        })
        return {
            b["key"]: int(b["total_qty"]["value"])
            for b in res["aggregations"]["by_item"]["buckets"]
        }
    except Exception as e:
        print(f"[FoodResQ] Error fetching all reservations: {e}")
        return {}


# ── Metrics ───────────────────────────────────────────────────────────────────

def get_metrics() -> dict:
    """Returns aggregate metrics used on the Impact dashboard."""
    try:
        es = get_client()
        ensure_index(es)

        agg_query = {
            "query": {"match_all": {}},
            "size": 0,
            "aggs": {
                "total_saving": {
                    "sum": {
                        "script": {
                            "source": "doc['price'].value - doc['discount_price'].value"
                        }
                    }
                },
                "avg_saving": {
                    "avg": {
                        "script": {
                            "source": "doc['price'].value - doc['discount_price'].value"
                        }
                    }
                },
                "total_qty": {
                    "sum": {"field": "quantity_available"}
                },
                "by_category": {
                    "terms": {"field": "category", "size": 20}
                },
            },
        }

        res  = es.search(index=INDEX, body=agg_query)
        aggs = res.get("aggregations", {})
        cats = {
            b["key"]: b["doc_count"]
            for b in aggs.get("by_category", {}).get("buckets", [])
        }

        all_reserved = get_all_active_reservations()
        total_reserved = sum(all_reserved.values())

        return {
            "total_items":    res["hits"]["total"]["value"],
            "total_saving":   aggs.get("total_saving", {}).get("value", 0) or 0,
            "avg_saving":     aggs.get("avg_saving",   {}).get("value", 0) or 0,
            "by_category":    cats,
            "total_qty":      int(aggs.get("total_qty", {}).get("value", 0) or 0),
            "total_reserved": total_reserved,
        }

    except Exception as e:
        print(f"[FoodResQ] Error fetching metrics: {e}")
        return {"total_items": 0, "total_saving": 0, "avg_saving": 0,
                "by_category": {}, "total_qty": 0, "total_reserved": 0}


# ── Seed data ─────────────────────────────────────────────────────────────────

def seed_data_if_empty():
    """
    Loads sample Singapore listings on first run.
    Safe to call on every startup — only seeds when the index is empty.
    """
    es = get_client()
    ensure_index(es)

    count = es.count(index=INDEX)["count"]
    if count > 0:
        return

    now = datetime.utcnow()

    seed_items = [
        {
            "title": "Butter Croissant Box (6 pcs)",
            "description": "Fresh unsold croissants from the evening batch. Perfectly flaky.",
            "merchant": "BakeHouse Tanjong Pagar",
            "price": 12.0, "discount_price": 5.0, "category": "Bakery",
            "quantity_available": 3,
            "location": {"lat": 1.2764, "lon": 103.8455},
            "pickup_end": (now + timedelta(hours=3)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Assorted Muffin Pack (4 pcs)",
            "description": "Blueberry and chocolate chip muffins baked this morning.",
            "merchant": "The Daily Grind Bugis",
            "price": 9.0, "discount_price": 4.0, "category": "Bakery",
            "quantity_available": 4,
            "location": {"lat": 1.3006, "lon": 103.8554},
            "pickup_end": (now + timedelta(hours=2)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Sushi Set (12 pcs)",
            "description": "End-of-day nigiri and maki — made fresh this afternoon.",
            "merchant": "Sakura Bento Raffles Place",
            "price": 22.0, "discount_price": 9.0, "category": "Japanese",
            "quantity_available": 2,
            "location": {"lat": 1.2834, "lon": 103.8516},
            "pickup_end": (now + timedelta(hours=1, minutes=30)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Chicken Pasta Box",
            "description": "Creamy carbonara with grilled chicken — full portion.",
            "merchant": "Pasta Republic Orchard",
            "price": 14.0, "discount_price": 6.0, "category": "Western",
            "quantity_available": 3,
            "location": {"lat": 1.3049, "lon": 103.8320},
            "pickup_end": (now + timedelta(hours=2, minutes=45)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Sandwich Wrap Combo",
            "description": "Tuna and egg mayo wraps with a bag of crisps.",
            "merchant": "Bites & Brews Dhoby Ghaut",
            "price": 10.0, "discount_price": 4.5, "category": "Cafe",
            "quantity_available": 5,
            "location": {"lat": 1.2990, "lon": 103.8455},
            "pickup_end": (now + timedelta(hours=2)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Char Siu Bao Set (5 pcs)",
            "description": "Steamed BBQ pork buns — end of lunch service.",
            "merchant": "Golden Palace Chinatown",
            "price": 8.0, "discount_price": 3.5, "category": "Asian",
            "quantity_available": 3,
            "location": {"lat": 1.2829, "lon": 103.8431},
            "pickup_end": (now + timedelta(hours=1)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Acai Bowl",
            "description": "Thick acai with granola and fresh fruit. Made an hour ago.",
            "merchant": "Bowls & Co Clarke Quay",
            "price": 13.0, "discount_price": 7.0, "category": "Cafe",
            "quantity_available": 2,
            "location": {"lat": 1.2896, "lon": 103.8461},
            "pickup_end": (now + timedelta(hours=1, minutes=30)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Poke Bowl (Large)",
            "description": "Salmon and tuna poke with edamame and sesame dressing.",
            "merchant": "Poke Theory City Hall",
            "price": 18.0, "discount_price": 8.0, "category": "Japanese",
            "quantity_available": 2,
            "location": {"lat": 1.2932, "lon": 103.8520},
            "pickup_end": (now + timedelta(hours=2)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Sourdough Loaf",
            "description": "Whole sourdough loaf baked this morning — half-price to clear.",
            "merchant": "Loafology Tiong Bahru",
            "price": 11.0, "discount_price": 5.5, "category": "Bakery",
            "quantity_available": 3,
            "location": {"lat": 1.2847, "lon": 103.8275},
            "pickup_end": (now + timedelta(hours=4)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Nasi Lemak Set",
            "description": "Coconut rice, sambal, egg, anchovies, and chicken wing.",
            "merchant": "Mamak Corner Lavender",
            "price": 8.0, "discount_price": 4.0, "category": "Asian",
            "quantity_available": 4,
            "location": {"lat": 1.3069, "lon": 103.8621},
            "pickup_end": (now + timedelta(hours=1)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Almond Croissant (3 pcs)",
            "description": "Twice-baked almond croissants — rich and nutty.",
            "merchant": "Maison Patisserie Orchard",
            "price": 14.0, "discount_price": 6.0, "category": "Bakery",
            "quantity_available": 3,
            "location": {"lat": 1.3069, "lon": 103.8318},
            "pickup_end": (now + timedelta(hours=2)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Teriyaki Chicken Bento",
            "description": "Grilled teriyaki chicken with Japanese rice and miso soup.",
            "merchant": "Bento Box Tanjong Pagar",
            "price": 16.0, "discount_price": 7.0, "category": "Japanese",
            "quantity_available": 2,
            "location": {"lat": 1.2764, "lon": 103.8440},
            "pickup_end": (now + timedelta(hours=1, minutes=45)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Fruit Tart Assortment (4 pcs)",
            "description": "Custard tarts topped with fresh seasonal fruit.",
            "merchant": "Sweet Endings Raffles Place",
            "price": 16.0, "discount_price": 7.0, "category": "Dessert",
            "quantity_available": 4,
            "location": {"lat": 1.2839, "lon": 103.8519},
            "pickup_end": (now + timedelta(hours=2)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Laksa Bowl",
            "description": "Rich coconut laksa broth with prawns and tofu puffs.",
            "merchant": "Spice Garden Bugis",
            "price": 10.0, "discount_price": 5.0, "category": "Asian",
            "quantity_available": 3,
            "location": {"lat": 1.3011, "lon": 103.8570},
            "pickup_end": (now + timedelta(hours=1)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Cheese Danish (3 pcs)",
            "description": "Flaky pastry with cream cheese filling — morning bake.",
            "merchant": "Corner Bakery Marina Bay",
            "price": 11.0, "discount_price": 4.5, "category": "Bakery",
            "quantity_available": 4,
            "location": {"lat": 1.2816, "lon": 103.8565},
            "pickup_end": (now + timedelta(hours=2, minutes=30)).isoformat(), "listed_at": now.isoformat(),
        },
    ]

    for item in seed_items:
        es.index(index=INDEX, document=item)

    es.indices.refresh(index=INDEX)
    print(f"[FoodResQ] Seeded {len(seed_items)} items into '{INDEX}'")
