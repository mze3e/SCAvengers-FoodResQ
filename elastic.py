"""
elastic.py – All OpenSearch interactions for FoodResQ.
Uses AWS IAM request signing via boto3 + requests-aws4auth.
"""

import os
import boto3
from datetime import datetime, timedelta
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

INDEX = "food_items"
REGION = os.getenv("AWS_REGION", "us-west-2")
_raw_url = os.getenv("ES_URL", "")
HOST = _raw_url.replace("https://", "").replace("http://", "").rstrip("/")


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
                "title":          {"type": "text"},
                "description":    {"type": "text"},
                "merchant":       {"type": "keyword"},
                "price":          {"type": "float"},
                "discount_price": {"type": "float"},
                "category":       {"type": "keyword"},
                "location":       {"type": "geo_point"},
                "pickup_end":     {"type": "date"},
                "listed_at":      {"type": "date"},
            }
        }
    }
    es.indices.create(index=INDEX, body=mapping)


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
        es.index(index=INDEX, document=doc)
        return True
    except Exception as e:
        print(f"[FoodResQ] Error indexing item: {e}")
        return False


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

        return {
            "total_items":   res["hits"]["total"]["value"],
            "total_saving":  aggs.get("total_saving", {}).get("value", 0) or 0,
            "avg_saving":    aggs.get("avg_saving",   {}).get("value", 0) or 0,
            "by_category":   cats,
        }

    except Exception as e:
        print(f"[FoodResQ] Error fetching metrics: {e}")
        return {"total_items": 0, "total_saving": 0, "avg_saving": 0, "by_category": {}}


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
            "location": {"lat": 1.2764, "lon": 103.8455},
            "pickup_end": (now + timedelta(hours=3)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Assorted Muffin Pack (4 pcs)",
            "description": "Blueberry and chocolate chip muffins baked this morning.",
            "merchant": "The Daily Grind Bugis",
            "price": 9.0, "discount_price": 4.0, "category": "Bakery",
            "location": {"lat": 1.3006, "lon": 103.8554},
            "pickup_end": (now + timedelta(hours=2)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Sushi Set (12 pcs)",
            "description": "End-of-day nigiri and maki — made fresh this afternoon.",
            "merchant": "Sakura Bento Raffles Place",
            "price": 22.0, "discount_price": 9.0, "category": "Japanese",
            "location": {"lat": 1.2834, "lon": 103.8516},
            "pickup_end": (now + timedelta(hours=1, minutes=30)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Chicken Pasta Box",
            "description": "Creamy carbonara with grilled chicken — full portion.",
            "merchant": "Pasta Republic Orchard",
            "price": 14.0, "discount_price": 6.0, "category": "Western",
            "location": {"lat": 1.3049, "lon": 103.8320},
            "pickup_end": (now + timedelta(hours=2, minutes=45)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Sandwich Wrap Combo",
            "description": "Tuna and egg mayo wraps with a bag of crisps.",
            "merchant": "Bites & Brews Dhoby Ghaut",
            "price": 10.0, "discount_price": 4.5, "category": "Cafe",
            "location": {"lat": 1.2990, "lon": 103.8455},
            "pickup_end": (now + timedelta(hours=2)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Char Siu Bao Set (5 pcs)",
            "description": "Steamed BBQ pork buns — end of lunch service.",
            "merchant": "Golden Palace Chinatown",
            "price": 8.0, "discount_price": 3.5, "category": "Asian",
            "location": {"lat": 1.2829, "lon": 103.8431},
            "pickup_end": (now + timedelta(hours=1)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Acai Bowl",
            "description": "Thick acai with granola and fresh fruit. Made an hour ago.",
            "merchant": "Bowls & Co Clarke Quay",
            "price": 13.0, "discount_price": 7.0, "category": "Cafe",
            "location": {"lat": 1.2896, "lon": 103.8461},
            "pickup_end": (now + timedelta(hours=1, minutes=30)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Poke Bowl (Large)",
            "description": "Salmon and tuna poke with edamame and sesame dressing.",
            "merchant": "Poke Theory City Hall",
            "price": 18.0, "discount_price": 8.0, "category": "Japanese",
            "location": {"lat": 1.2932, "lon": 103.8520},
            "pickup_end": (now + timedelta(hours=2)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Sourdough Loaf",
            "description": "Whole sourdough loaf baked this morning — half-price to clear.",
            "merchant": "Loafology Tiong Bahru",
            "price": 11.0, "discount_price": 5.5, "category": "Bakery",
            "location": {"lat": 1.2847, "lon": 103.8275},
            "pickup_end": (now + timedelta(hours=4)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Nasi Lemak Set",
            "description": "Coconut rice, sambal, egg, anchovies, and chicken wing.",
            "merchant": "Mamak Corner Lavender",
            "price": 8.0, "discount_price": 4.0, "category": "Asian",
            "location": {"lat": 1.3069, "lon": 103.8621},
            "pickup_end": (now + timedelta(hours=1)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Almond Croissant (3 pcs)",
            "description": "Twice-baked almond croissants — rich and nutty.",
            "merchant": "Maison Patisserie Orchard",
            "price": 14.0, "discount_price": 6.0, "category": "Bakery",
            "location": {"lat": 1.3069, "lon": 103.8318},
            "pickup_end": (now + timedelta(hours=2)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Teriyaki Chicken Bento",
            "description": "Grilled teriyaki chicken with Japanese rice and miso soup.",
            "merchant": "Bento Box Tanjong Pagar",
            "price": 16.0, "discount_price": 7.0, "category": "Japanese",
            "location": {"lat": 1.2764, "lon": 103.8440},
            "pickup_end": (now + timedelta(hours=1, minutes=45)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Fruit Tart Assortment (4 pcs)",
            "description": "Custard tarts topped with fresh seasonal fruit.",
            "merchant": "Sweet Endings Raffles Place",
            "price": 16.0, "discount_price": 7.0, "category": "Dessert",
            "location": {"lat": 1.2839, "lon": 103.8519},
            "pickup_end": (now + timedelta(hours=2)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Laksa Bowl",
            "description": "Rich coconut laksa broth with prawns and tofu puffs.",
            "merchant": "Spice Garden Bugis",
            "price": 10.0, "discount_price": 5.0, "category": "Asian",
            "location": {"lat": 1.3011, "lon": 103.8570},
            "pickup_end": (now + timedelta(hours=1)).isoformat(), "listed_at": now.isoformat(),
        },
        {
            "title": "Cheese Danish (3 pcs)",
            "description": "Flaky pastry with cream cheese filling — morning bake.",
            "merchant": "Corner Bakery Marina Bay",
            "price": 11.0, "discount_price": 4.5, "category": "Bakery",
            "location": {"lat": 1.2816, "lon": 103.8565},
            "pickup_end": (now + timedelta(hours=2, minutes=30)).isoformat(), "listed_at": now.isoformat(),
        },
    ]

    for item in seed_items:
        es.index(index=INDEX, document=item)

    es.indices.refresh(index=INDEX)
    print(f"[FoodResQ] Seeded {len(seed_items)} items into '{INDEX}'")
