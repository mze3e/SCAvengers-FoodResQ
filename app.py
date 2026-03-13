import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_geolocation import streamlit_geolocation
from dummy_elastic import (  # swap back to `elastic` when ES is available
    search_food_items,
    add_food_item,
    get_metrics,
    seed_data_if_empty,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FoodResQ",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Brand colours */
  :root {
    --green-dark:  #2C5F2D;
    --green-mid:   #3B6D11;
    --green-light: #97BC62;
    --cream:       #F7F5F0;
  }
  .stTabs [data-baseweb="tab-list"] { gap: 8px; }
  .stTabs [data-baseweb="tab"] {
    background: #f0f0f0; border-radius: 6px 6px 0 0;
    padding: 8px 20px; font-weight: 600;
  }
  .stTabs [aria-selected="true"] {
    background: var(--green-dark) !important;
    color: white !important;
  }
  .food-card {
    background: white; border-radius: 10px;
    border: 1px solid #e0e0e0; padding: 16px;
    margin-bottom: 12px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
  }
  .food-card h4 { margin: 0 0 4px; color: #1a2e1b; }
  .price-tag {
    display: inline-block; background: #EAF3DE;
    color: #2C5F2D; font-weight: 700;
    padding: 2px 10px; border-radius: 20px; font-size: 0.95em;
  }
  .original-price { text-decoration: line-through; color: #999; font-size: 0.85em; }
  .distance-tag { color: #666; font-size: 0.85em; }
  .category-badge {
    display: inline-block; background: #f0f4ff;
    color: #3a5bbf; font-size: 0.78em; font-weight: 600;
    padding: 2px 8px; border-radius: 10px; margin-left: 6px;
  }
  .metric-box {
    background: var(--green-dark); color: white;
    border-radius: 10px; padding: 20px; text-align: center;
  }
  .metric-box .num { font-size: 2.4em; font-weight: 800; }
  .metric-box .lbl { font-size: 0.85em; opacity: 0.85; margin-top: 4px; }
  header[data-testid="stHeader"] { background: #2C5F2D; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🥗 FoodResQ")
st.markdown("*Making surplus food discoverable in real time.*")
st.divider()

# ── Session state defaults (geo prefill only — not tied to widget keys) ───────
st.session_state.setdefault("_geo_lat", 1.2830)
st.session_state.setdefault("_geo_lon", 103.8513)

# ── Seed on first load ────────────────────────────────────────────────────────
with st.spinner("Connecting to Elasticsearch..."):
    try:
        seed_data_if_empty()
    except Exception as e:
        st.error(f"❌ Could not connect to Elasticsearch: {e}")
        st.info("Check your `.env` file — see `README.md` for setup instructions.")
        st.stop()

# ── Geolocation (one call only — library hardcodes key="loc") ─────────────────
_geo_col, _ = st.columns([1, 5])
with _geo_col:
    _loc = streamlit_geolocation()
    if isinstance(_loc, dict) and _loc.get("latitude") is not None:
        st.session_state["_geo_lat"] = float(_loc["latitude"])
        st.session_state["_geo_lon"] = float(_loc["longitude"])

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_search, tab_add, tab_metrics = st.tabs(["🔍  Search Food", "➕  Add Listing", "📊  Impact"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 – SEARCH
# ══════════════════════════════════════════════════════════════════════════════
with tab_search:
    st.subheader("Find surplus food near you")

    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
    with col1:
        keyword = st.text_input("Search", placeholder="croissant, sushi, sandwich…", label_visibility="collapsed")
    with col2:
        lat = st.number_input("Your latitude", value=st.session_state["_geo_lat"], format="%.4f", step=0.0001)
    with col3:
        lon = st.number_input("Your longitude", value=st.session_state["_geo_lon"], format="%.4f", step=0.0001)
    with col4:
        radius_km = st.selectbox("Radius", [1, 2, 5, 10], index=1)

    if st.button("🔍 Search", type="primary", use_container_width=True):
        with st.spinner("Searching nearby listings…"):
            results = search_food_items(
                keyword=keyword,
                lat=lat,
                lon=lon,
                radius_km=radius_km,
            )

        if not results:
            st.info("No items found nearby. Try a wider radius or different keyword.")
        else:
            st.success(f"Found **{len(results)}** item(s) within {radius_km} km")
            for item in results:
                src  = item["_source"]
                dist = item.get("sort", [None])[0]
                dist_str = f"{dist/1000:.1f} km away" if dist else ""
                pickup_raw = src.get("pickup_end", "")
                try:
                    pickup_dt = datetime.fromisoformat(pickup_raw)
                    pickup_str = pickup_dt.strftime("Pick up by %H:%M")
                except Exception:
                    pickup_str = pickup_raw

                saving = src.get("price", 0) - src.get("discount_price", 0)

                st.markdown(f"""
                <div class="food-card">
                  <h4>{src.get('title','')}<span class="category-badge">{src.get('category','')}</span></h4>
                  <div style="margin:4px 0 6px">
                    <span class="price-tag">S${src.get('discount_price',''):.2f}</span>
                    &nbsp;<span class="original-price">S${src.get('price',''):.2f}</span>
                    &nbsp;💰 Save S${saving:.2f}
                  </div>
                  <div style="color:#555;font-size:0.9em">{src.get('description','')}</div>
                  <div style="margin-top:8px;display:flex;gap:16px;font-size:0.85em;color:#666">
                    <span>🏪 {src.get('merchant','')}</span>
                    <span>📍 {dist_str}</span>
                    <span>⏰ {pickup_str}</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.caption("Enter a keyword or leave blank to browse all nearby listings, then hit Search.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – ADD LISTING
# ══════════════════════════════════════════════════════════════════════════════
with tab_add:
    st.subheader("List surplus food")

    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            title         = st.text_input("Item name *", placeholder="Butter Croissant Box")
            merchant      = st.text_input("Merchant name *", placeholder="BakeHouse Tanjong Pagar")
            description   = st.text_area("Description", placeholder="Fresh unsold croissants from evening batch", height=90)
            category      = st.selectbox("Category", ["Bakery", "Cafe", "Japanese", "Western", "Asian", "Dessert", "Other"])
        with c2:
            price          = st.number_input("Original price (S$)", min_value=0.5, max_value=500.0, value=12.0, step=0.5)
            discount_price = st.number_input("Discounted price (S$)", min_value=0.5, max_value=500.0, value=5.0, step=0.5)
            lat_add        = st.number_input("Latitude *", value=st.session_state["_geo_lat"], format="%.4f", step=0.0001)
            lon_add        = st.number_input("Longitude *", value=st.session_state["_geo_lon"], format="%.4f", step=0.0001)
            pickup_hours   = st.slider("Pickup window (hours from now)", 1, 8, 3)

        submitted = st.form_submit_button("📦 Publish listing", type="primary", use_container_width=True)

    if submitted:
        if not title or not merchant:
            st.error("Item name and merchant name are required.")
        elif discount_price >= price:
            st.warning("Discounted price should be less than the original price.")
        else:
            pickup_end = (datetime.utcnow() + timedelta(hours=pickup_hours)).isoformat()
            doc = {
                "title":          title,
                "description":    description,
                "merchant":       merchant,
                "price":          price,
                "discount_price": discount_price,
                "category":       category,
                "location":       {"lat": lat_add, "lon": lon_add},
                "pickup_end":     pickup_end,
                "listed_at":      datetime.utcnow().isoformat(),
            }
            with st.spinner("Indexing into Elasticsearch…"):
                result = add_food_item(doc)
            if result:
                st.success(f"✅ **{title}** listed successfully! It's now discoverable by nearby users.")
                st.balloons()
            else:
                st.error("Failed to index item. Check the Elasticsearch connection.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 – METRICS
# ══════════════════════════════════════════════════════════════════════════════
with tab_metrics:
    st.subheader("Impact dashboard")

    with st.spinner("Loading metrics…"):
        metrics = get_metrics()

    total        = metrics.get("total_items", 0)
    avg_saving   = metrics.get("avg_saving", 0)
    total_saving = metrics.get("total_saving", 0)
    by_category  = metrics.get("by_category", {})

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-box"><div class="num">{total}</div><div class="lbl">Listings active</div></div>', unsafe_allow_html=True)
    with m2:
        est_meals = total  # 1 listing ≈ 1 meal rescued
        st.markdown(f'<div class="metric-box"><div class="num">{est_meals}</div><div class="lbl">Estimated meals rescued</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-box"><div class="num">S${total_saving:.0f}</div><div class="lbl">Total savings unlocked</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-box"><div class="num">S${avg_saving:.2f}</div><div class="lbl">Avg saving per item</div></div>', unsafe_allow_html=True)

    st.divider()

    if by_category:
        st.markdown("#### Listings by category")
        df = pd.DataFrame(
            [{"Category": k, "Count": v} for k, v in sorted(by_category.items(), key=lambda x: -x[1])]
        )
        st.bar_chart(df.set_index("Category"))
    else:
        st.info("No data yet. Add some listings to see metrics.")
