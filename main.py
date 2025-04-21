import streamlit as st
import requests
import json
from datetime import datetime, timezone
import pytz
import plotly.graph_objects as go
import os
from streamlit.components.v1 import iframe

# --- Constants ---
BASE_URL_IQAIR_V2 = "https://api.airvisual.com/v2"
YOUR_LOCAL_TIMEZONE = "Asia/Dhaka"
BANGLADESH_FLAG_URL = "https://flagcdn.com/w40/bd.png"

# --- Page Config ---
st.set_page_config(
    page_title="Clean Air Bangladesh",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Load CSS ---
def load_css(file_name):
    # (Keep load_css function as before)
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        css_file_path = os.path.join(script_dir, file_name)
        if not os.path.exists(css_file_path): css_file_path = file_name # Fallback
        if os.path.exists(css_file_path):
            with open(css_file_path) as f:
                st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
        else:
             st.error(f"CSS file '{file_name}' not found.")
    except Exception as e:
         st.error(f"Error loading CSS file '{file_name}': {e}")

load_css("style.css") # Load the new dark blue theme styles

# --- Session State Initialization ---
default_agent_url = "https://elevenlabs.io/app/talk-to?agent_id=rHhQqxWxk4pue21ttj6s"
if 'agent_url' not in st.session_state: st.session_state.agent_url = default_agent_url
if 'countries' not in st.session_state: st.session_state.countries = []
if 'states' not in st.session_state: st.session_state.states = []
if 'cities' not in st.session_state: st.session_state.cities = []
if 'selected_country' not in st.session_state: st.session_state.selected_country = None
if 'selected_state' not in st.session_state: st.session_state.selected_state = None
if 'selected_city' not in st.session_state: st.session_state.selected_city = None
if 'aqi_result' not in st.session_state: st.session_state.aqi_result = None
if 'last_api_fetch_time_utc' not in st.session_state: st.session_state.last_api_fetch_time_utc = None
if 'user_api_key' not in st.session_state: st.session_state.user_api_key = ""

# --- API & Helper Functions ---
# (Keep get_supported_countries, get_supported_states, get_supported_cities,
#  get_iqair_detailed_data, get_aqi_details, time_ago, create_simplified_aqi_gauge
#  functions as defined in the PREVIOUS corrected version)
# --- API Data Fetching Functions (Cached Lists) ---
@st.cache_data(ttl=3600) # Cache for 1 hour
def get_supported_countries(api_key):
    if not api_key: return []
    url = f"{BASE_URL_IQAIR_V2}/countries"
    params = {'key': api_key}
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            countries = sorted([item.get("country") for item in data.get("data", []) if item.get("country")])
            return countries if countries else [] # Ensure always list
        else:
            print(f"API Error fetching countries: {data.get('data', {}).get('message')}")
            return []
    except Exception as e:
        print(f"Error fetching countries list: {e}")
        return [] # Return empty list on any exception

@st.cache_data(ttl=3600)
def get_supported_states(country, api_key):
    if not api_key or not country: return []
    url = f"{BASE_URL_IQAIR_V2}/states"
    params = {'country': country, 'key': api_key}
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            states = sorted([item.get("state") for item in data.get("data", []) if item.get("state")])
            return states if states else []
        else:
            print(f"API Error fetching states for {country}: {data.get('data', {}).get('message')}")
            return []
    except Exception as e:
        print(f"Error fetching states for {country}: {e}")
        return []

@st.cache_data(ttl=3600)
def get_supported_cities(state, country, api_key):
    if not api_key or not state or not country: return []
    url = f"{BASE_URL_IQAIR_V2}/cities"
    params = {'state': state, 'country': country, 'key': api_key}
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            cities = sorted([item.get("city") for item in data.get("data", []) if item.get("city")])
            return cities if cities else []
        else:
            print(f"API Error fetching cities for {state}, {country}: {data.get('data', {}).get('message')}")
            return []
    except Exception as e:
        print(f"Error fetching cities for {state}, {country}: {e}")
        return []

# Function to Get City Air Quality & Weather Data
# Use @st.cache_data with caution if you need immediate refresh after button click
# @st.cache_data(ttl=900) # Cache for 15 mins might be better
def get_iqair_detailed_data(city, state, country, api_key):
    if not all([city, state, country, api_key]): return None
    url = f"{BASE_URL_IQAIR_V2}/city"
    params = {'city': city.strip(), 'state': state.strip(), 'country': country.strip(), 'key': api_key.strip()}
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            fetch_time_utc = datetime.now(timezone.utc)
            result = {"status": "success", "fetch_timestamp_utc": fetch_time_utc}
            d = data.get("data", {})
            c = d.get("current", {})
            p = c.get("pollution", {})
            w = c.get("weather", {})
            result.update({
                "city_returned": d.get("city"), "state_returned": d.get("state"), "country_returned": d.get("country"),
                "aqi_us": p.get("aqius"), "main_pollutant_us": p.get("mainus"), "timestamp_str": p.get("ts"),
                "temperature_c": w.get("tp"), "humidity_percent": w.get("hu"), "wind_speed_mps": w.get("ws"),
                "wind_direction_deg": w.get("wd"), "weather_icon_code": w.get("ic")
            })
            result["pollutants"] = {k: v.get('conc') for k, v in p.items() if isinstance(v, dict) and 'conc' in v}
            result["timestamp_utc"] = None
            if result["timestamp_str"]:
                try: result["timestamp_utc"] = datetime.fromisoformat(result["timestamp_str"].replace('Z', '+00:00'))
                except: pass
            return result
        else:
            return {"status": "error", "error_message": data.get('data', {}).get('message', 'Unknown API error')}
    except requests.exceptions.Timeout:
        return {"status": "error", "error_message": "Request timed out."}
    except requests.exceptions.HTTPError as e:
         error_msg = f"API HTTP Error: {e.response.status_code}"
         if e.response.status_code in [401, 403]: error_msg += " (Invalid API Key?)"
         elif e.response.status_code == 400: error_msg += " (Bad Request - Check Location?)"
         elif e.response.status_code == 429: error_msg += " (API Rate Limit Exceeded)"
         return {"status": "error", "error_message": error_msg}
    except Exception as e:
        print(f"Unexpected error fetching data: {e}")
        return {"status": "error", "error_message": "An unexpected error occurred."}

# --- AQI Category and Health Tip ---
def get_aqi_details(aqi_us):
    # (Keep the same function as before)
    if aqi_us is None: return ("Unknown", "--", "#8892b0", "Data unavailable.", "unknown") # Secondary text color
    try: aqi_val = int(aqi_us)
    except: return ("Invalid", "--", "#8892b0", "Invalid AQI format.", "invalid")
    if 0 <= aqi_val <= 50: return ("Good", "0-50", "#64ffda", "Air quality is satisfactory. Enjoy activities!", "good") # Cyan
    elif 51 <= aqi_val <= 100: return ("Moderate", "51-100", "#fdd750", "Sensitive groups may consider reducing heavy exertion.", "moderate") # Yellow
    elif 101 <= aqi_val <= 150: return ("Unhealthy for Sensitive Groups", "101-150", "#ffae57", "Sensitive groups should reduce outdoor activity.", "uhfsg") # Orange
    elif 151 <= aqi_val <= 200: return ("Unhealthy", "151-200", "#ff7b8a", "Everyone should reduce heavy exertion. Sensitive groups avoid outdoors.", "unhealthy") # Reddish
    elif 201 <= aqi_val <= 300: return ("Very Unhealthy", "201-300", "#c08aee", "Everyone should avoid heavy exertion. Sensitive groups stay indoors.", "very-unhealthy") # Purple
    elif aqi_val >= 301: return ("Hazardous", "301+", "#c78194", "Everyone should avoid all outdoor activity.", "hazardous") # Maroon/Brownish
    else: return ("Invalid", "--", "#8892b0", "AQI value out of range.", "invalid")

# --- Time Ago Function ---
def time_ago(dt_utc):
    # (Keep the same function as before)
    if not isinstance(dt_utc, datetime): return "N/A"
    if dt_utc.tzinfo is None: dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    diff = now_utc - dt_utc; seconds = diff.total_seconds()
    if seconds < 0: return "just now"
    if seconds < 10: return "just now"
    elif seconds < 60: return f"{int(seconds)}s ago" # Shorter format
    elif seconds < 3600: minutes = int(seconds / 60); return f"{minutes}m ago"
    elif seconds < 86400: hours = int(seconds / 3600); return f"{hours}h ago"
    else: days = int(seconds / 86400); return f"{days}d ago"

# --- Simplified Gauge Chart Function ---
def create_simplified_aqi_gauge(aqi_value, category_color):
    if aqi_value is None: return None

    # Define the text color directly using the hex code
    gauge_number_color = "#ccd6f6" # Corresponds to --text-primary-light

    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = aqi_value,
        domain = {'x': [0, 1], 'y': [0, 1]},
        gauge = {
            'axis': {'range': [0, 500], 'visible': False},
            'bar': {'color': category_color, 'thickness': 0.4},
            'bgcolor': "#172a45", # secondary dark blue
            'borderwidth': 0,
            'steps': [ # Subtle steps background
                {'range': [0, 50], 'color': "#1f3a5f"},
                {'range': [50, 100], 'color': "#2a4a6f"},
                {'range': [100, 150], 'color': "#355a7f"},
                {'range': [150, 200], 'color': "#406a8f"},
                {'range': [200, 300], 'color': "#4b7aa0"},
                {'range': [300, 500], 'color': "#568ac0"}
            ],
            'threshold': {
                'line': {'color': "#8892b0", 'width': 3}, # Use secondary text color for threshold line
                'thickness': 0.8,
                'value': aqi_value
            }
        },
        # --- FIX: Use the Python variable for color ---
        number = {
            'font': {'size': 48, 'color': gauge_number_color, 'family': "Roboto, sans-serif"},
            'suffix': ""
        }
        # --- End Fix ---
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=150,
        margin=dict(l=10, r=10, t=10, b=10)
    )
    # No need for update_traces if color is set correctly in 'number' dict
    return fig

# ==============================================================================
# --- STREAMLIT APP UI ---
# ==============================================================================

# --- Custom Header ---
st.markdown(
    f"""
    <div class="custom-header">
        <div class="title-section">
            <img src="{BANGLADESH_FLAG_URL}" alt="BD Flag" class="flag-icon">
            <h1>Clean Air Bangladesh</h1>
        </div>
        <div class="header-icons">
            <!-- Icons are visual placeholders -->
            <span class="icon-button" title="Settings (Configure Below)">⚙️</span>
            <span class="icon-button" title="Share (Not Implemented)">🔗</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
st.caption("Note: Header icons are placeholders. Configure API Key & Agent URL below.") # Clarify limitation

# --- Combined Banner Image and AI Agent Section ---
st.markdown('<div class="top-content-area" style="padding: 1rem 1rem 0 1rem;">', unsafe_allow_html=True) # Optional wrapper

# Agent Title and Mic Info (Placed above the columns)
st.markdown("##### Talk to AI Agent") # Smaller heading
st.info("""
    🎙️ **Microphone Access:** Your browser will ask for microphone permission **when you interact with the agent below.**
    """, icon="ℹ️")

col_image, col_agent = st.columns([0.6, 0.4], gap="large") # 60% / 40% split with a larger gap

with col_image:
    banner_path = "clean_banner.png"
    if os.path.exists(banner_path):
        st.image(banner_path, use_container_width=True)
    else:
        # Placeholder if image missing
        st.markdown("<div style='background-color:#172a45; height: 350px; display: flex; align-items: center; justify-content: center; border-radius: 8px;'><span style='color:#8892b0;'>Banner Image Area</span></div>", unsafe_allow_html=True)
        st.caption("Optional: Place 'clean_banner.png' in the app directory.")

with col_agent:
    # Get URL from state
    agent_url = st.session_state.get('agent_url', "")

    # Apply container styling for the agent column
    st.markdown('<div class="agent-column-container">', unsafe_allow_html=True) # New class for specific styling

    if agent_url and "elevenlabs.io/app/talk-to" in agent_url:
        st.markdown('<div class="agent-iframe-wrapper">', unsafe_allow_html=True)
        try:
            # Use a height that potentially aligns better with the banner, may need adjustment
            iframe(agent_url, height=350, scrolling=False)
        except Exception as e:
            st.error(f"Could not load agent: {e}")
        st.markdown('</div>', unsafe_allow_html=True) # Close wrapper
    else:
        # Show prompt message if URL is missing/invalid
        st.warning("Enter a valid Agent URL in 'Settings' below to activate.", icon="⚙️")
        # Add placeholder visual
        st.markdown("<div style='background-color:#172a45; height: 350px; display: flex; align-items: center; justify-content: center; border-radius: 8px;'><span style='color:#8892b0;'>AI Agent Area</span></div>", unsafe_allow_html=True)


    st.markdown('</div>', unsafe_allow_html=True) # Close agent-column-container

st.markdown('</div>', unsafe_allow_html=True) # Close top-content-area
st.divider() # Add separator


# --- Location Selector Bar ---
st.markdown('<div class="location-selector-bar">', unsafe_allow_html=True)
# Adjusted column ratios for better button alignment
sel_cols = st.columns([2.5, 2.5, 2.5, 1, 1.5]) # Added spacer column, adjusted button width

# --- Settings moved to Expander (shown below location bar) ---

# Spacer for API Key popover button
with sel_cols[0]:
     with st.popover("🔑 API Key"):
        st.markdown("**IQAir API Key**")
        api_key_input = st.text_input(
            "Enter Key:", type="password", label_visibility="collapsed",
            value=st.session_state.get("user_api_key", ""),
            key="api_key_input_popover"
        )
        # Update session state only if value changes to avoid unnecessary reruns
        if api_key_input != st.session_state.user_api_key:
            st.session_state.user_api_key = api_key_input
            st.rerun() # Rerun required to update main view based on key presence

        if not st.session_state.user_api_key:
            st.info("An IQAir API Key is needed.", icon="ℹ️")
        else:
            st.success("API Key present.", icon="✔️")


if not st.session_state.user_api_key:
     # Span placeholder text across multiple columns for visibility
     with sel_cols[1]: st.markdown("<span style='color:#8892b0;'>Enter API Key to Select Location</span>", unsafe_allow_html=True)
     with sel_cols[2]: pass # Empty column
     with sel_cols[3]: pass # Empty column
     with sel_cols[4]: st.button("Get Data", disabled=True, key="get_data_btn_disabled", use_container_width=True)

else:
    # Fetch countries if needed
    if not st.session_state.countries:
        st.session_state.countries = get_supported_countries(st.session_state.user_api_key)

    countries_list = st.session_state.countries
    if countries_list is None: countries_list = []
    country_options = [""] + countries_list
    default_country_index = country_options.index("Bangladesh") if "Bangladesh" in country_options else 0

    with sel_cols[1]: # Start select boxes from second column
        st.markdown("<label>Country</label>", unsafe_allow_html=True)
        selected_country = st.selectbox("Country", options=country_options, index=default_country_index, key="country_selector", label_visibility="collapsed")

    # State Selection
    if selected_country != st.session_state.selected_country:
        st.session_state.selected_country = selected_country; st.session_state.selected_state = None; st.session_state.selected_city = None
        st.session_state.states = []; st.session_state.cities = []
        if selected_country:
            with st.spinner(f"Loading states..."):
                st.session_state.states = get_supported_states(selected_country, st.session_state.user_api_key)
        st.rerun()

    states_list = st.session_state.states
    if states_list is None: states_list = []
    state_options = [""] + states_list
    current_state_index = state_options.index(st.session_state.selected_state) if st.session_state.selected_state in state_options else 0
    with sel_cols[2]:
         st.markdown("<label>State / Region</label>", unsafe_allow_html=True)
         selected_state = st.selectbox("State / Region", options=state_options, index=current_state_index, key="state_selector", label_visibility="collapsed", disabled=not selected_country or not states_list)

    # City Selection
    if selected_state != st.session_state.selected_state:
         st.session_state.selected_state = selected_state; st.session_state.selected_city = None
         st.session_state.cities = []
         if selected_state and selected_country:
             with st.spinner(f"Loading cities..."):
                st.session_state.cities = get_supported_cities(selected_state, selected_country, st.session_state.user_api_key)
         st.rerun()

    cities_list = st.session_state.cities
    if cities_list is None: cities_list = []
    city_options = [""] + cities_list
    current_city_index = city_options.index(st.session_state.selected_city) if st.session_state.selected_city in city_options else 0
    with sel_cols[3]:
        st.markdown("<label>City</label>", unsafe_allow_html=True)
        selected_city = st.selectbox("City", options=city_options, index=current_city_index, key="city_selector", label_visibility="collapsed", disabled=not selected_state or not cities_list)
        if selected_city != st.session_state.selected_city:
            st.session_state.selected_city = selected_city

    # Fetch Data Button
    with sel_cols[4]:
        st.markdown("<label> </label>", unsafe_allow_html=True) # Spacer label for alignment
        if st.button("Get Data", key="get_data_btn", use_container_width=True): # Use container width
            current_selection = { "country": st.session_state.selected_country, "state": st.session_state.selected_state, "city": st.session_state.selected_city }
            if not all(current_selection.values()):
                st.toast("⚠️ Please select a Country, State, and City.", icon="⚠️")
            else:
                # Clear previous results before fetching new ones
                # st.session_state.aqi_result = None
                # st.session_state.last_api_fetch_time_utc = None
                # st.rerun() # Show spinner immediately

                with st.spinner("Fetching data..."):
                     result = get_iqair_detailed_data(current_selection["city"], current_selection["state"], current_selection["country"], st.session_state.user_api_key)
                     st.session_state.aqi_result = result
                     if result and result.get("status") == "success":
                         st.session_state.last_api_fetch_time_utc = result.get("fetch_timestamp_utc")
                         st.toast("Data updated!", icon="✅")
                     else:
                         error_msg = result.get("error_message", "Failed to fetch data") if result else "Failed to fetch data"
                         st.toast(f"❌ {error_msg}", icon="❌")
                         st.session_state.last_api_fetch_time_utc = None
                     # No need to rerun here, display logic below will use the updated session state
st.markdown('</div>', unsafe_allow_html=True) # Close location-selector-bar


# --- Settings Expander ---
with st.expander("⚙️ Settings & Configuration"):
    st.markdown("**API Key**")
    st.info("Your IQAir API Key is managed via the '🔑 API Key' button above.")

    st.markdown("**Agent URL**")
    agent_url_input = st.text_input(
        "Enter ElevenLabs Agent URL:",
        value=st.session_state.get('agent_url', default_agent_url),
        key="agent_url_input_expander",
        label_visibility="collapsed"
    )
    if agent_url_input != st.session_state.agent_url:
        st.session_state.agent_url = agent_url_input
        st.success("Agent URL updated.", icon="🔗")
        st.rerun() # Rerun if URL changes to update iframe if visible

# --- Main Content Area (Cards) ---
# (Keep the logic for defining aqi_card_content and weather_card_content
#  and displaying the cards in columns col1, col2 as in the PREVIOUS corrected version)
# --- Main Content Area (Cards) ---
st.markdown('<div class="cards-container">', unsafe_allow_html=True)
col1, col2 = st.columns(2)
# (Default content setup)
aqi_card_content = {"title": "Air Quality", "value": "--", "category": "No data", "recommendation": "Select location & click 'Get Data'.", "color": "#8892b0", "timestamp": None, "aqi_val": None}
weather_card_content = {"title": "Weather", "temp": "--", "humidity": "--", "wind_speed": "--", "wind_dir": "--", "timestamp": None}
# (Process results if available)
if st.session_state.aqi_result and st.session_state.aqi_result.get("status") == "success":
    res = st.session_state.aqi_result
    loc_name = res.get("city_returned") or st.session_state.selected_city or "Selected Location"
    aqi_val = res.get("aqi_us")
    category, _, color, recommendation, _ = get_aqi_details(aqi_val)
    aqi_card_content = { "title": f"Air Quality in {loc_name}", "value": str(aqi_val) if aqi_val is not None else "--", "category": category, "recommendation": recommendation, "color": color, "timestamp": res.get("timestamp_utc"), "aqi_val": aqi_val }
    weather_card_content = { "title": f"Weather in {loc_name}", "temp": f"{res.get('temperature_c')}°C" if res.get('temperature_c') is not None else "--", "humidity": f"{res.get('humidity_percent')}%" if res.get('humidity_percent') is not None else "--", "wind_speed": f"{res.get('wind_speed_mps')} m/s" if res.get('wind_speed_mps') is not None else "--", "wind_dir": f"{res.get('wind_direction_deg')}°" if res.get('wind_direction_deg') is not None else "--", "timestamp": res.get("timestamp_utc"), }
elif st.session_state.aqi_result and st.session_state.aqi_result.get("status") == "error":
     error_msg = st.session_state.aqi_result.get("error_message", "Failed to load data.")
     aqi_card_content["category"] = "Error"; aqi_card_content["recommendation"] = f"Could not load data: {error_msg}"

# (AQI Card Display)
with col1:
    st.markdown('<div class="info-card aqi-card">', unsafe_allow_html=True)
    st.markdown(f'<h3 class="card-title">{aqi_card_content["title"]}</h3>', unsafe_allow_html=True)
    gauge_fig = create_simplified_aqi_gauge(aqi_card_content["aqi_val"], aqi_card_content["color"])
    if gauge_fig: st.plotly_chart(gauge_fig, use_container_width=True, config={'displayModeBar': False})
    else:
        aqi_value_display = aqi_card_content["value"]; aqi_color_display = aqi_card_content["color"] if aqi_card_content["aqi_val"] is not None else "#8892b0"
        st.markdown(f'<div class="aqi-display" style="text-align: center; margin-bottom: 1rem;"><span class="aqi-value" style="font-size: 48px; font-weight: 700; color:{aqi_color_display};">{aqi_value_display}</span></div>', unsafe_allow_html=True)
    st.markdown(f'<p class="aqi-category" style="text-align: center; font-size: 14px; color: #8892b0; margin-top: -0.5rem; margin-bottom: 1.5rem;">{aqi_card_content["category"]}</p>', unsafe_allow_html=True)
    rec_html = '<p class="health-recommendation" style="font-size: 14px; font-style: italic; color: #8892b0; line-height: 1.5; display: flex; align-items: center; margin-bottom: 1rem;">'
    aqi_numeric = None
    try: aqi_numeric = int(aqi_card_content.get("aqi_val"))
    except: pass
    if aqi_numeric is not None and aqi_numeric > 100: rec_html += '<span class="warning-icon" title="Warning" style="color: var(--accent-yellow); font-size: 16px; margin-right: 8px;">⚠️</span>'
    rec_html += f'{aqi_card_content["recommendation"]}</p>'
    st.markdown(rec_html, unsafe_allow_html=True)
    ts = aqi_card_content["timestamp"]; fetch_ts = st.session_state.last_api_fetch_time_utc
    ts_str = f"Sensor: {time_ago(ts)}" if ts else "Sensor: N/A"; fetch_ts_str = f"Fetched: {time_ago(fetch_ts)}" if fetch_ts else ""
    combined_ts_str = f"{ts_str} | {fetch_ts_str}" if fetch_ts else ts_str
    st.markdown(f'<p class="timestamp">{combined_ts_str}</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# (Weather Card Display)
with col2:
    st.markdown('<div class="info-card weather-card">', unsafe_allow_html=True)
    st.markdown(f'<h3 class="card-title">{weather_card_content["title"]}</h3>', unsafe_allow_html=True)
    st.markdown('<div class="weather-grid">', unsafe_allow_html=True)
    st.markdown('<div class="weather-metric-box"><span class="metric-icon">🌡️</span><span class="metric-value">{}</span><span class="metric-label">Temperature</span></div>'.format(weather_card_content['temp']), unsafe_allow_html=True)
    st.markdown('<div class="weather-metric-box"><span class="metric-icon">💧</span><span class="metric-value">{}</span><span class="metric-label">Humidity</span></div>'.format(weather_card_content['humidity']), unsafe_allow_html=True)
    st.markdown('<div class="weather-metric-box"><span class="metric-icon">💨</span><span class="metric-value">{}</span><span class="metric-label">Wind Speed</span></div>'.format(weather_card_content['wind_speed']), unsafe_allow_html=True)
    st.markdown('<div class="weather-metric-box"><span class="metric-icon">🧭</span><span class="metric-value">{}</span><span class="metric-label">Wind Direction</span></div>'.format(weather_card_content['wind_dir']), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    ts = weather_card_content["timestamp"]; fetch_ts = st.session_state.last_api_fetch_time_utc
    ts_str = f"Sensor: {time_ago(ts)}" if ts else "Sensor: N/A"; fetch_ts_str = f"Fetched: {time_ago(fetch_ts)}" if fetch_ts else ""
    combined_ts_str = f"{ts_str} | {fetch_ts_str}" if fetch_ts else ts_str
    st.markdown(f'<p class="timestamp">{combined_ts_str}</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True) # Close cards-container


# --- AQI Explanation Accordion ---
# (Keep the expander code as before)
with st.expander("Learn About AQI"):
    st.markdown(""" <ul class="aqi-explanation-list"> ... </ul> """, unsafe_allow_html=True) # Keep list content



# --- Footer ---
st.markdown(
    """
    <div class="footer">
        <p>App by MD Mahbubur Rahman for Clean Bangladesh 2025</p>
        <a href="#" target="_blank">Privacy Policy</a> <!-- Add actual link -->
    </div>
    """,
    unsafe_allow_html=True
)