import uuid
import requests
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from streamlit_geolocation import streamlit_geolocation
from elastic import (
    search_food_items,
    add_food_item,
    get_metrics,
    seed_data_if_empty,
    reserve_item,
    cancel_reservation,
    get_my_reservations,
    get_available_qty,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FoodResQ",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Reverse geocoding (Nominatim / OpenStreetMap — free, no key needed) ───────
@st.cache_data(ttl=300)
def get_location_name(lat: float, lon: float) -> str:
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json"},
            headers={"User-Agent": "FoodResQ/1.0"},
            timeout=4,
        )
        addr = r.json().get("address", {})
        parts = [
            addr.get("road") or addr.get("pedestrian"),
            addr.get("suburb") or addr.get("neighbourhood"),
            addr.get("city") or addr.get("town") or addr.get("village"),
        ]
        return ", ".join(p for p in parts if p)
    except Exception:
        return ""


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
    margin-bottom: 4px;
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
  .avail-badge {
    display: inline-block; font-size: 0.78em; font-weight: 600;
    padding: 2px 10px; border-radius: 10px;
  }
  .avail-green  { background: #d4edda; color: #155724; }
  .avail-yellow { background: #fff3cd; color: #856404; }
  .avail-red    { background: #f8d7da; color: #721c24; }
  .qty-bar-bg {
    background: #e9ecef; border-radius: 4px; height: 8px; margin-top: 4px;
  }
  .qty-bar-fill {
    height: 8px; border-radius: 4px;
  }
  .reservation-box {
    background: #e8f4f8; border: 1px solid #bee5eb;
    border-radius: 8px; padding: 10px 14px;
    margin-bottom: 10px;
  }
  .reservation-box .r-title { font-weight: 700; color: #0c5460; }
  .reservation-box .r-meta  { font-size: 0.85em; color: #555; margin-top: 2px; }
  .timer-pill {
    display: inline-block; background: #fff3cd; color: #856404;
    font-size: 0.78em; font-weight: 600;
    padding: 2px 8px; border-radius: 10px; border: 1px solid #ffc107;
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

# ── Session state defaults ────────────────────────────────────────────────────
st.session_state.setdefault("_geo_lat", 1.2830)
st.session_state.setdefault("_geo_lon", 103.8513)
st.session_state.setdefault("_session_id", str(uuid.uuid4()))
st.session_state.setdefault("_search_results", [])

SESSION_ID = st.session_state["_session_id"]

# ── Seed on first load ────────────────────────────────────────────────────────
with st.spinner("Connecting to Elasticsearch..."):
    try:
        seed_data_if_empty()
    except Exception as e:
        st.error(f"❌ Could not connect to Elasticsearch: {e}")
        st.info("Check your `.env` file — see `README.md` for setup instructions.")
        st.stop()

# ── Sidebar — geolocation ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📍 My Location")
    _loc = streamlit_geolocation()
    if isinstance(_loc, dict) and _loc.get("latitude") is not None:
        st.session_state["_geo_lat"] = float(_loc["latitude"])
        st.session_state["_geo_lon"] = float(_loc["longitude"])
    name = get_location_name(st.session_state["_geo_lat"], st.session_state["_geo_lon"])
    st.caption(f"**Lat** {st.session_state['_geo_lat']:.4f}  **Lon** {st.session_state['_geo_lon']:.4f}")
    if name:
        st.caption(f"📌 {name}")
    st.info("Press the button to auto-fill your coordinates in Search and Add Listing.")

    st.divider()
    st.markdown("### 🛒 My Reservations")
    my_sidebar_reservations = get_my_reservations(SESSION_ID)
    if my_sidebar_reservations:
        for r in my_sidebar_reservations:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            secs_left = max(0, int((r["expires_at"] - now).total_seconds()))
            mins_left  = secs_left // 60
            secs_rem   = secs_left % 60
            st.markdown(
                f"**{r['item_title'][:28]}**  \n"
                f"Qty: {r['qty']} · ⏳ {mins_left}m {secs_rem}s left"
            )
        st.caption(f"{len(my_sidebar_reservations)} active reservation(s)")
    else:
        st.caption("No active reservations.")

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

    search_loc_name = get_location_name(lat, lon)
    if search_loc_name:
        st.caption(f"📌 Searching near **{search_loc_name}**")

    if st.button("🔍 Search", type="primary", use_container_width=True):
        with st.spinner("Searching nearby listings…"):
            st.session_state["_search_results"] = search_food_items(
                keyword=keyword, lat=lat, lon=lon, radius_km=radius_km,
            )

    results = st.session_state["_search_results"]

    if not results:
        st.caption("Enter a keyword or leave blank to browse all nearby listings, then hit Search.")
    else:
        # Fresh reservation state for this render pass
        my_reservations = get_my_reservations(SESSION_ID)
        my_reserved_ids = {r["item_id"] for r in my_reservations}

        st.success(f"Found **{len(results)}** item(s) within {radius_km} km")

        for item in results:
            item_id = item.get("_id", "")
            src     = item["_source"]
            dist    = item.get("sort", [None])[0]
            dist_str = f"{dist/1000:.1f} km away" if dist else ""

            pickup_raw = src.get("pickup_end", "")
            try:
                pickup_dt  = datetime.fromisoformat(pickup_raw)
                pickup_str = pickup_dt.strftime("Pick up by %H:%M")
            except Exception:
                pickup_str = pickup_raw

            saving    = src.get("price", 0) - src.get("discount_price", 0)
            total_qty = src.get("quantity_available", 1)

            # Live availability (recalculated every render)
            available = get_available_qty(item_id) if item_id else total_qty
            reserved  = total_qty - available
            reserved_pct = int((reserved / total_qty) * 100) if total_qty > 0 else 0

            # Colour-coded availability
            if available == 0:
                avail_class = "avail-red"
                avail_icon  = "🔴"
                avail_text  = "Fully reserved"
                bar_color   = "#dc3545"
            elif available <= 1 or (total_qty > 1 and available / total_qty <= 0.33):
                avail_class = "avail-yellow"
                avail_icon  = "🟡"
                avail_text  = f"{available} left — going fast!"
                bar_color   = "#f0a500"
            else:
                avail_class = "avail-green"
                avail_icon  = "🟢"
                avail_text  = f"{available} of {total_qty} available"
                bar_color   = "#2C5F2D"

            st.markdown(f"""
            <div class="food-card">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px">
                <h4 style="margin:0">{src.get('title','')}<span class="category-badge">{src.get('category','')}</span></h4>
                <span class="avail-badge {avail_class}">{avail_icon} {avail_text}</span>
              </div>
              <div style="margin:6px 0">
                <span class="price-tag">S${src.get('discount_price',0):.2f}</span>
                &nbsp;<span class="original-price">S${src.get('price',0):.2f}</span>
                &nbsp;💰 Save S${saving:.2f}
              </div>
              <div style="color:#555;font-size:0.9em">{src.get('description','')}</div>
              <div style="margin-top:8px;display:flex;gap:16px;font-size:0.85em;color:#666">
                <span>🏪 {src.get('merchant','')}</span>
                <span>📍 {dist_str}</span>
                <span>⏰ {pickup_str}</span>
              </div>
              <div style="margin-top:10px">
                <div style="display:flex;justify-content:space-between;font-size:0.75em;color:#888;margin-bottom:3px">
                  <span>📦 Quantity claimed</span>
                  <span>{reserved} reserved / {total_qty} total</span>
                </div>
                <div class="qty-bar-bg">
                  <div class="qty-bar-fill" style="background:{bar_color};width:{reserved_pct}%"></div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # ── Reservation controls (native Streamlit below the card) ────────
            user_res = next((r for r in my_reservations if r["item_id"] == item_id), None)

            if user_res:
                # Show current reservation + cancel option
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                secs_left = max(0, int((user_res["expires_at"] - now).total_seconds()))
                mins_left  = secs_left // 60
                secs_rem   = secs_left % 60
                col_info, col_cancel = st.columns([4, 1])
                with col_info:
                    st.success(
                        f"✅ You reserved **{user_res['qty']}** unit(s) · "
                        f"⏳ Expires in **{mins_left}m {secs_rem}s**"
                    )
                with col_cancel:
                    if st.button("✕ Cancel", key=f"cancel_{item_id}", use_container_width=True):
                        cancel_reservation(item_id, SESSION_ID)
                        st.rerun()

            elif available > 0:
                # Show reserve controls
                col_qty, col_btn, col_hint = st.columns([1, 2, 3])
                with col_qty:
                    qty_to_reserve = st.number_input(
                        "Qty", min_value=1, max_value=available, value=1,
                        key=f"qty_{item_id}", label_visibility="collapsed"
                    )
                with col_btn:
                    if st.button(
                        "🛒 Reserve (30 min)",
                        key=f"reserve_{item_id}",
                        type="primary",
                        use_container_width=True,
                    ):
                        result = reserve_item(item_id, qty_to_reserve, SESSION_ID)
                        if result["success"]:
                            st.toast(f"✅ {result['message']}! Hold expires in 30 min.", icon="🛒")
                            st.rerun()
                        else:
                            st.error(result["message"])
                with col_hint:
                    if available <= 2:
                        st.warning(f"⚠️ Only {available} left — act fast!")
                    else:
                        st.caption(f"Reserve up to {available} unit(s) for 30 minutes.")

            else:
                st.error("🔴 All units are currently reserved. Check back when holds expire.")

            st.markdown("<div style='margin-bottom:14px'></div>", unsafe_allow_html=True)

        # ── My Active Reservations summary ────────────────────────────────────
        my_reservations_fresh = get_my_reservations(SESSION_ID)
        if my_reservations_fresh:
            st.divider()
            st.markdown("### 📋 My Active Reservations")
            st.caption("These holds last 30 minutes from the time you reserved. Show this screen when picking up.")

            for r in my_reservations_fresh:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                secs_left = max(0, int((r["expires_at"] - now).total_seconds()))
                mins_left  = secs_left // 60
                secs_rem   = secs_left % 60
                total_cost = r["qty"] * r["discount_price"]

                col_res, col_res_cancel = st.columns([5, 1])
                with col_res:
                    st.markdown(f"""
                    <div class="reservation-box">
                      <div class="r-title">🛒 {r['item_title']}</div>
                      <div class="r-meta">
                        🏪 {r['merchant']} &nbsp;·&nbsp;
                        Qty: <strong>{r['qty']}</strong> &nbsp;·&nbsp;
                        Total: <strong>S${total_cost:.2f}</strong> &nbsp;·&nbsp;
                        <span class="timer-pill">⏳ {mins_left}m {secs_rem}s remaining</span>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_res_cancel:
                    st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
                    if st.button("Cancel", key=f"my_cancel_{r['item_id']}", use_container_width=True):
                        cancel_reservation(r["item_id"], SESSION_ID)
                        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – ADD LISTING
# ══════════════════════════════════════════════════════════════════════════════
with tab_add:
    st.subheader("List surplus food")

    add_loc_name = get_location_name(st.session_state["_geo_lat"], st.session_state["_geo_lon"])
    if add_loc_name:
        st.caption(f"📌 Listing location: **{add_loc_name}** — adjust coordinates below if needed.")

    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            title         = st.text_input("Item name *", placeholder="Butter Croissant Box")
            merchant      = st.text_input("Merchant name *", placeholder="BakeHouse Tanjong Pagar")
            description   = st.text_area("Description", placeholder="Fresh unsold croissants from evening batch", height=90)
            category      = st.selectbox("Category", ["Bakery", "Cafe", "Japanese", "Western", "Asian", "Dessert", "Other"])
        with c2:
            price            = st.number_input("Original price (S$)", min_value=0.5, max_value=500.0, value=12.0, step=0.5)
            discount_price   = st.number_input("Discounted price (S$)", min_value=0.5, max_value=500.0, value=5.0, step=0.5)
            quantity_listing = st.number_input("Quantity available", min_value=1, max_value=50, value=5, step=1,
                                               help="How many units / portions are you listing?")
            lat_add          = st.number_input("Latitude *", value=st.session_state["_geo_lat"], format="%.4f", step=0.0001)
            lon_add          = st.number_input("Longitude *", value=st.session_state["_geo_lon"], format="%.4f", step=0.0001)
            pickup_hours     = st.slider("Pickup window (hours from now)", 1, 8, 3)

        submitted = st.form_submit_button("📦 Publish listing", type="primary", use_container_width=True)

    if submitted:
        if not title or not merchant:
            st.error("Item name and merchant name are required.")
        elif discount_price >= price:
            st.warning("Discounted price should be less than the original price.")
        else:
            _now = datetime.now(timezone.utc).replace(tzinfo=None)
            pickup_end = (_now + timedelta(hours=pickup_hours)).isoformat()
            doc = {
                "title":              title,
                "description":        description,
                "merchant":           merchant,
                "price":              price,
                "discount_price":     discount_price,
                "category":           category,
                "quantity_available": int(quantity_listing),
                "location":           {"lat": lat_add, "lon": lon_add},
                "pickup_end":         pickup_end,
                "listed_at":          _now.isoformat(),
            }
            with st.spinner("Indexing into Elasticsearch…"):
                result = add_food_item(doc)
            if result:
                st.success(
                    f"✅ **{title}** listed successfully with **{int(quantity_listing)}** unit(s)! "
                    "It's now discoverable by nearby users."
                )
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

    total         = metrics.get("total_items", 0)
    avg_saving    = metrics.get("avg_saving", 0)
    total_saving  = metrics.get("total_saving", 0)
    by_category   = metrics.get("by_category", {})
    total_qty     = metrics.get("total_qty", 0)
    total_reserved = metrics.get("total_reserved", 0)
    total_available = max(0, total_qty - total_reserved)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-box"><div class="num">{total}</div><div class="lbl">Listings active</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-box"><div class="num">S${total_saving:.0f}</div><div class="lbl">Total savings unlocked</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-box"><div class="num">S${avg_saving:.2f}</div><div class="lbl">Avg saving per item</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-box"><div class="num">{total_reserved}</div><div class="lbl">Active reservations</div></div>', unsafe_allow_html=True)

    st.divider()

    # ── Quantity availability overview ────────────────────────────────────────
    if total_qty > 0:
        st.markdown("#### 📦 Overall quantity availability")
        reserved_pct = int((total_reserved / total_qty) * 100)
        available_pct = 100 - reserved_pct

        col_bar, col_legend = st.columns([3, 1])
        with col_bar:
            st.markdown(f"""
            <div style="margin-bottom:6px;font-size:0.9em;color:#555">
              <strong>{total_available}</strong> of <strong>{total_qty}</strong> total units available across all listings
            </div>
            <div style="background:#e9ecef;border-radius:6px;height:20px;position:relative;overflow:hidden">
              <div style="background:#2C5F2D;width:{available_pct}%;height:20px;border-radius:6px 0 0 6px;
                          display:flex;align-items:center;padding-left:8px;color:white;font-size:0.75em;font-weight:700">
                {available_pct}% free
              </div>
            </div>
            <div style="display:flex;gap:16px;margin-top:6px;font-size:0.8em;color:#666">
              <span>🟢 {total_available} available</span>
              <span>🟠 {total_reserved} reserved</span>
              <span>📦 {total_qty} total</span>
            </div>
            """, unsafe_allow_html=True)
        with col_legend:
            st.metric("Reserved now", total_reserved, delta=None)

    st.divider()

    if by_category:
        st.markdown("#### Listings by category")
        df = pd.DataFrame(
            [{"Category": k, "Count": v} for k, v in sorted(by_category.items(), key=lambda x: -x[1])]
        )
        st.bar_chart(df.set_index("Category"))
    else:
        st.info("No data yet. Add some listings to see metrics.")
