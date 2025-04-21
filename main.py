import streamlit as st
import requests
import json
from datetime import datetime, timezone, timedelta
import pytz # For local time display
import plotly.graph_objects as go
import os
import time # For time difference calculation
from streamlit.components.v1 import iframe


# --- Constants ---
BASE_URL_IQAIR_V2 = "https://api.airvisual.com/v2"
# IMPORTANT: Set to your local timezone string (e.g., 'Asia/Dhaka', 'America/New_York')
# Find valid names: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
YOUR_LOCAL_TIMEZONE = "Asia/Dhaka"

# --- Page Config (MUST be the first st command) ---
st.set_page_config(
    page_title="Smart Air Quality - Bangladesh",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Session State Initialization ---
# (Keep all previous session state initializations: theme, locations, data, etc.)
if 'theme' not in st.session_state: st.session_state.theme = 'dark'
if 'countries' not in st.session_state: st.session_state.countries = []
if 'states' not in st.session_state: st.session_state.states = []
if 'cities' not in st.session_state: st.session_state.cities = []
if 'selected_country' not in st.session_state: st.session_state.selected_country = None
if 'selected_state' not in st.session_state: st.session_state.selected_state = None
if 'selected_city' not in st.session_state: st.session_state.selected_city = None
if 'aqi_result' not in st.session_state: st.session_state.aqi_result = None
if 'last_api_fetch_time_utc' not in st.session_state: st.session_state.last_api_fetch_time_utc = None # Renamed for clarity
if 'current_aqi_class' not in st.session_state: st.session_state.current_aqi_class = 'aqi-unknown'
if 'agent_url' not in st.session_state:
    st.session_state.agent_url = "" # Initialize empty agent URL

# --- Load CSS Function ---
# (Keep the load_css function as before)
def load_css(file_name):
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        css_file_path = os.path.join(script_dir, file_name)

        if not os.path.exists(css_file_path):
            css_file_path = file_name
            if not os.path.exists(css_file_path):
                 st.error(f"CSS file '{file_name}' not found in script directory or current directory.")
                 return

        with open(css_file_path) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

    except Exception as e:
         st.error(f"Error loading CSS file '{file_name}': {e}")

# --- Apply Theme ---
css_file = "style_dark.css" if st.session_state.theme == 'dark' else "style_light.css"
load_css(css_file)

# --- API Data Fetching Functions (Cached Lists) ---
# (Keep get_supported_countries, get_supported_states, get_supported_cities as before)
@st.cache_data(ttl=3600)
def get_supported_countries(api_key):
    # (function content)
    if not api_key: return []
    url = f"{BASE_URL_IQAIR_V2}/countries"
    params = {'key': api_key}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            countries = sorted([item.get("country") for item in data.get("data", []) if item.get("country")])
            return countries
        else:
            msg = f"API Error fetching countries: {data.get('data', {}).get('message')}"
            st.warning(msg, icon="⚠️")
            return []
    except Exception as e:
        st.error(f"Error fetching countries list: {e}")
        return []

@st.cache_data(ttl=3600)
def get_supported_states(country, api_key):
    # (function content)
    if not api_key or not country: return []
    url = f"{BASE_URL_IQAIR_V2}/states"
    params = {'country': country, 'key': api_key}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            states = sorted([item.get("state") for item in data.get("data", []) if item.get("state")])
            return states
        else:
            msg = f"API Error fetching states for {country}: {data.get('data', {}).get('message')}"
            st.warning(msg, icon="⚠️")
            return []
    except Exception as e:
        st.error(f"Error fetching states list for {country}: {e}")
        return []

@st.cache_data(ttl=3600)
def get_supported_cities(state, country, api_key):
    # (function content)
    if not api_key or not state or not country: return []
    url = f"{BASE_URL_IQAIR_V2}/cities"
    params = {'state': state, 'country': country, 'key': api_key}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            cities = sorted([item.get("city") for item in data.get("data", []) if item.get("city")])
            return cities
        else:
            msg = f"API Error fetching cities for {state}, {country}: {data.get('data', {}).get('message')}"
            st.warning(msg, icon="⚠️")
            return []
    except Exception as e:
        st.error(f"Error fetching cities list for {state}, {country}: {e}")
        return []


# --- Function to Get City Air Quality & Weather Data ---
def get_iqair_detailed_data(city, state, country, api_key):
    # (Keep the core logic the same as the previous version)
    # Ensure it returns the 'fetch_timestamp_utc' and 'timestamp_utc' fields correctly
    if not all([city, state, country, api_key]):
        print("Error: Missing required fields for AQI fetch.")
        return None

    url = f"{BASE_URL_IQAIR_V2}/city"
    params = {
        'city': city.strip(), 'state': state.strip(),
        'country': country.strip(), 'key': api_key.strip()
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            # **Record the time WE fetched the data**
            fetch_time_utc = datetime.now(timezone.utc)
            result = {"status": "success", "fetch_timestamp_utc": fetch_time_utc}
            result["data"] = data.get("data", {})
            current_data = result["data"].get("current", {})
            pollution_data = current_data.get("pollution", {})
            weather_data = current_data.get("weather", {})

            # Extract fields (AQI, Weather, Location)
            result["aqi_us"] = pollution_data.get("aqius")
            result["main_pollutant_us"] = pollution_data.get("mainus")
            result["timestamp_str"] = pollution_data.get("ts") # **API's timestamp string**
            result["temperature_c"] = weather_data.get("tp")
            result["pressure_hpa"] = weather_data.get("pr")
            result["humidity_percent"] = weather_data.get("hu")
            result["wind_speed_mps"] = weather_data.get("ws")
            result["wind_direction_deg"] = weather_data.get("wd")
            result["weather_icon"] = weather_data.get("ic")
            result["city_returned"] = result["data"].get("city", city)
            result["state_returned"] = result["data"].get("state", state)
            result["country_returned"] = result["data"].get("country", country)

            # Extract detailed pollutants (as before)
            pollutants = {}
            # ... (pollutant extraction logic remains the same) ...
             # Look for common pollutants (keys might vary slightly based on API versions)
            # 'p2' = PM2.5, 'p1' = PM10, 'o3' = Ozone, 'n2' = NO2, 's2' = SO2, 'co' = CO
            # The values are usually concentrations (e.g., ug/m3)
            # We primarily use the main pollutant ('mainus') and AQI ('aqius')
            # but store others if available
            pollution_details = pollution_data.get('details', {}) # Check if details exist

            def get_pollutant_value(key):
                # Helper to safely get concentration
                 pollutant_info = pollution_data.get(key)
                 if isinstance(pollutant_info, dict):
                     return pollutant_info.get('conc')
                 return None # Or handle other formats if needed

            # Map common keys to display names and attempt extraction
            pollutant_map = {
                 'p2': 'PM2.5', 'p1': 'PM10', 'o3': 'Ozone (O₃)',
                 'n2': 'Nitrogen Dioxide (NO₂)', 's2': 'Sulphur Dioxide (SO₂)',
                 'co': 'Carbon Monoxide (CO)'
             }
            for key, name in pollutant_map.items():
                value = get_pollutant_value(key)
                if value is not None:
                    pollutants[name] = value # Store with readable name

            result["pollutants"] = pollutants

            # Convert API timestamp string to datetime object
            result["timestamp_utc"] = None
            result["timestamp_formatted"] = "N/A"
            if result["timestamp_str"]:
                try:
                    dt_obj_utc = datetime.fromisoformat(result["timestamp_str"].replace('Z', '+00:00'))
                    result["timestamp_utc"] = dt_obj_utc # Store UTC datetime object
                    result["timestamp_formatted"] = dt_obj_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
                except (ValueError, TypeError) as e:
                    print(f"Warning: Could not parse timestamp '{result['timestamp_str']}': {e}")
                    result["timestamp_formatted"] = result["timestamp_str"] # Fallback

            if result["aqi_us"] is None:
                 result["status"] = "error"; result["error_message"] = "AQI value missing."

            return result

        else: # API returned status != success
            error_message = data.get("data", {}).get("message", "Unknown API error")
            st.error(f"IQAir API Error: {error_message}")
            return {"status": "error", "error_message": error_message}

    # (Keep the exception handling blocks as before)
    except requests.exceptions.Timeout as e:
        st.error("Error: The request to IQAir timed out.")
        return {"status": "error", "error_message": "Request timed out."}
    except requests.exceptions.HTTPError as e:
        msg = f"HTTP Error {response.status_code}."
        if response.status_code in [401, 403]: msg = "Invalid IQAir API Key or permission denied."
        elif response.status_code == 400: msg = "Bad request. Check selected City/State/Country or API key format."
        elif response.status_code == 404: msg = "Specific city data not found by IQAir."
        else: msg = f"HTTP Error {response.status_code}: {response.text[:100]}..." # Include snippet of error
        st.error(f"API Error: {msg}")
        return {"status": "error", "error_message": msg}
    except requests.exceptions.RequestException as e:
        st.error("Error: Could not connect to IQAir API. Check internet connection.")
        return {"status": "error", "error_message": f"Network connection failed: {e}"}
    except json.JSONDecodeError as e:
         st.error("Error: Received an invalid response from IQAir API.")
         return {"status": "error", "error_message": f"Invalid API response format: {e}"}
    except Exception as e:
        st.error(f"An unexpected error occurred processing data: {e}")
        return {"status": "error", "error_message": f"Unexpected error: {e}"}

# --- Health Tip Functions ---
# (Keep get_health_tip_us_aqi_base as before)
def get_health_tip_us_aqi_base(aqi_us):
    if aqi_us is None: return "⚪ Data unavailable.", "", "aqi-unknown"
    try: aqi_val = int(aqi_us)
    except (ValueError, TypeError): return "⚪ Invalid AQI data format.", "", "aqi-unknown"

    if 0 <= aqi_val <= 50: return "Minimal risk. Enjoy outdoor activities!", "✅", "aqi-good"
    elif 51 <= aqi_val <= 100: return "Sensitive groups consider reducing prolonged or heavy exertion outdoors.", "🟡", "aqi-moderate"
    elif 101 <= aqi_val <= 150: return "Sensitive groups should reduce prolonged or heavy exertion outdoors. General public may start feeling effects.", "🟠", "aqi-uhfsg" # Unhealthy for Sensitive Groups
    elif 151 <= aqi_val <= 200: return "Everyone reduce heavy exertion. Sensitive groups avoid prolonged outdoor activity.", "🔴", "aqi-unhealthy"
    elif 201 <= aqi_val <= 300: return "Everyone avoid heavy exertion outdoors. Sensitive groups should remain indoors.", "🟣", "aqi-very-unhealthy"
    elif aqi_val >= 301: return "Everyone should avoid all outdoor physical activity. Remain indoors and keep activity levels low.", "🟤", "aqi-hazardous"
    else: return "⚪ Invalid AQI value.", "", "aqi-unknown"

# (Keep get_dynamic_health_recommendation as before - its logic was okay)
def get_dynamic_health_recommendation(result_data):
    if not result_data or result_data.get("status") != "success":
        return "Select a location to get recommendations."

    aqi_us = result_data.get("aqi_us")
    temp_c = result_data.get("temperature_c")
    humidity = result_data.get("humidity_percent")
    main_pollutant = result_data.get('main_pollutant_us', 'N/A')

    base_tip, emoji, aqi_class = get_health_tip_us_aqi_base(aqi_us)
    # Start with Markdown H3 for the title within the card
    recommendation = f"### {emoji} Health Recommendation (US AQI: {aqi_us if aqi_us is not None else 'N/A'})"
    recommendation += f"\n\n**General Advice:** {base_tip}"
    recommendation += f"\n\n*(Main Pollutant reported: {main_pollutant})*" # Use two newlines for paragraph break

    # Add weather-related context
    additional_tips = []
    if aqi_us is not None:
        try: # Ensure AQI is usable
            aqi_val = int(aqi_us)
            if aqi_val > 100 and temp_c is not None and temp_c > 30:
                additional_tips.append("High heat combined with poor air quality increases health risks. Stay cool and hydrated.")
            if aqi_val > 50 and humidity is not None and humidity > 75:
                 additional_tips.append("High humidity can make breathing feel more difficult, especially with moderate or worse air quality.")
            if aqi_val <= 50 and temp_c is not None and temp_c < 5:
                 additional_tips.append("Air quality is good, but dress warmly for the cold weather if going outside.")
        except (ValueError, TypeError):
            pass # Ignore weather tips if AQI is invalid

    if additional_tips:
        recommendation += "\n\n**Additional Considerations:**" # Bolder title
        for tip in additional_tips:
            recommendation += f"\n- _{tip}_" # Italicize tips

    return recommendation

# --- AQI Gauge Chart Function ---
# (Keep create_aqi_gauge as before)
def create_aqi_gauge(aqi_value, theme):
    # (function content)
    if aqi_value is None: return None
    ranges = [0, 50, 100, 150, 200, 300, 501]
    colors = ["#00e400", "#ffff00", "#ff7e00", "#ff0000", "#8f3f97", "#7e0023"]
    bar_color = "#cccccc"; gauge_bg_color = "#2a2a2a"; axis_color = "#f0f0f0";
    threshold_color = "#ff00ff"; number_color = "#00ffdd"; font_color = "#f0f0f0"
    if theme == 'light':
        gauge_bg_color = "#ffffff"; axis_color = "#333333"; threshold_color = "#dc3545";
        number_color = "#007bff"; font_color = "#1a1a1a"
    for i in range(len(ranges) - 1):
        if ranges[i] <= aqi_value < ranges[i+1]: bar_color = colors[i]; break
    if aqi_value == 0: bar_color = colors[0]
    if aqi_value >= ranges[-2]: bar_color = colors[-1]
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = aqi_value,
        title = {'text': "<b>US AQI Level</b>", 'font': {'size': 20, 'color': number_color}},
        number = {'font': {'color': number_color, 'size': 40}},
        domain = {'x': [0, 1], 'y': [0, 1]},
        gauge = {
            'axis': {'range': [0, 500], 'tickwidth': 1, 'tickcolor': axis_color},
            'bar': {'color': bar_color, 'thickness': 0.3}, 'bgcolor': gauge_bg_color,
            'borderwidth': 1, 'bordercolor': axis_color,
            'steps': [ {'range': [0, 50], 'color': colors[0]}, {'range': [50, 100], 'color': colors[1]},
                       {'range': [100, 150], 'color': colors[2]}, {'range': [150, 200], 'color': colors[3]},
                       {'range': [200, 300], 'color': colors[4]}, {'range': [300, 500], 'color': colors[5]}],
            'threshold': {'line': {'color': threshold_color, 'width': 4}, 'thickness': 0.75, 'value': aqi_value } } ))
    fig.update_layout( paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font={'color': font_color}, height=250, margin=dict(l=20, r=20, t=50, b=20) )
    return fig

# --- Developer Profile Function ---
# (Keep show_developer_profile as before, using the container and CSS class)
def show_developer_profile():
    st.sidebar.subheader("👨‍💻 Developer Profile")
    with st.sidebar.container(): # Use Streamlit container
        # Add the custom class for CSS targeting if needed, but try without first
        # st.markdown('<div class="developer-profile-box">', unsafe_allow_html=True)
        profile_image_path = "mts-upimg.png"
        script_dir = os.path.dirname(os.path.abspath(__file__))
        image_full_path = os.path.join(script_dir, profile_image_path)
        if os.path.exists(image_full_path):
             st.image(image_full_path, width=100)
        else: st.caption("Profile image not found.")
        st.markdown("**Name:** MD MAHBUBUR RAHMAN")
        st.markdown("**Contact:** mail.mdmahbuburrahman@gmail.com")
        st.markdown(
            """[GitHub](...) | [LinkedIn](...) | [Facebook](...) | [Portfolio](...)""", # Shortened for brevity
            unsafe_allow_html=True)
        st.info("Passionate about data, environment, and building helpful tools.")
        # st.markdown('</div>', unsafe_allow_html=True) # End div if using HTML injection

# --- Function to get AQI Level Class Name ---
# (Keep get_aqi_class as before)
def get_aqi_class(aqi_us):
    if aqi_us is None: return "aqi-unknown"
    try: aqi_val = int(aqi_us)
    except (ValueError, TypeError): return "aqi-unknown"
    if 0 <= aqi_val <= 50: return "aqi-good"
    elif 51 <= aqi_val <= 100: return "aqi-moderate"
    elif 101 <= aqi_val <= 150: return "aqi-uhfsg"
    elif 151 <= aqi_val <= 200: return "aqi-unhealthy"
    elif 201 <= aqi_val <= 300: return "aqi-very-unhealthy"
    elif aqi_val >= 301: return "aqi-hazardous"
    else: return "aqi-unknown"


# --- Function to format time difference (Improved Clarity) ---
def time_ago(dt_utc):
    if not isinstance(dt_utc, datetime): # Check if valid datetime
        return "N/A"
    # Ensure the datetime is timezone-aware (UTC)
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc) # Assume UTC if naive

    now_utc = datetime.now(timezone.utc)
    diff = now_utc - dt_utc
    seconds = diff.total_seconds()

    if seconds < 0: # Timestamp is in the future? Handle gracefully.
        return "just now"
    if seconds < 10:
        return "just now"
    elif seconds < 60:
        return f"{int(seconds)} seconds ago"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    else:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days > 1 else ''} ago"


# ==============================================================================
# --- STREAMLIT APP UI ---
# ==============================================================================

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Configuration")
    # Theme Toggle Button (as before)
    theme_icon = "☀️" if st.session_state.theme == 'dark' else "🌙"
    theme_tooltip = "Switch to Light Mode" if st.session_state.theme == 'dark' else "Switch to Dark Mode"
    if st.button(f"{theme_icon} {theme_tooltip}", key="theme_toggle"):
        st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'
        st.rerun()

    # API Key Input (as before)
    user_api_key = st.text_input("Enter your IQAir API Key:", type="password", help="Required to fetch data.")
    st.markdown("[Get your free IQAir API key here](...)", unsafe_allow_html=True)
    st.divider()
    # Developer Profile (as before)
    show_developer_profile()

# --- Main Area ---
st.title("🌍💨 Smart Air Quality Analyzer for Clean Bangladesh 🇧🇩")

# --- Banner Image ---
# (Keep banner image logic as before)
banner_image_path = "air_quality_banner.png"
# ... (rest of banner logic) ...
script_dir = os.path.dirname(os.path.abspath(__file__))
banner_full_path = os.path.join(script_dir, banner_image_path)
if os.path.exists(banner_full_path):
    st.image(banner_full_path, use_column_width=True)
else:
    st.caption("Banner image (air_quality_banner.png) not found.")


st.markdown("Select a location and click 'Get Air Quality Data' to see the results.")
st.divider()

# --- Location Selection ---
# (Keep location selection logic with columns and selectboxes as before)
# Ensure st.rerun() is used appropriately after country/state changes to update dropdowns
col_loc1, col_loc2, col_loc3 = st.columns(3)

if not user_api_key:
    st.warning("Please enter your IQAir API key in the sidebar to load location options.")
    # Clear dependent dropdowns if API key is removed
    st.session_state.countries = []; st.session_state.states = []; st.session_state.cities = []
    st.session_state.selected_country = None; st.session_state.selected_state = None; st.session_state.selected_city = None
else:
    # Trigger fetching countries if key is present and list is empty
    if not st.session_state.countries:
         st.session_state.countries = get_supported_countries(user_api_key)

    country_options = [""] + st.session_state.countries
    default_country_index = 0
    if "Bangladesh" in st.session_state.countries:
        default_country_index = country_options.index("Bangladesh")

    with col_loc1:
        selected_country = st.selectbox("1. Country:", options=country_options, index=default_country_index, key="country_selector")

    # State Selection
    if selected_country != st.session_state.selected_country:
        st.session_state.selected_country = selected_country
        st.session_state.selected_state = None; st.session_state.selected_city = None
        st.session_state.states = []; st.session_state.cities = []
        if selected_country:
            with st.spinner(f"Loading states for {selected_country}..."):
                st.session_state.states = get_supported_states(selected_country, user_api_key)
        st.rerun() # Rerun to refresh state options

    state_options = [""] + st.session_state.states
    current_state_index = 0
    if st.session_state.selected_state and st.session_state.selected_state in state_options:
        current_state_index = state_options.index(st.session_state.selected_state)

    with col_loc2:
        selected_state = st.selectbox("2. State / Region:", options=state_options, index=current_state_index, key="state_selector", disabled=not selected_country or not st.session_state.states)

    # City Selection
    if selected_state != st.session_state.selected_state:
        st.session_state.selected_state = selected_state
        st.session_state.selected_city = None
        st.session_state.cities = []
        if selected_state and selected_country:
             with st.spinner(f"Loading cities for {selected_state}..."):
                st.session_state.cities = get_supported_cities(selected_state, selected_country, user_api_key)
        st.rerun() # Rerun to refresh city options

    city_options = [""] + st.session_state.cities
    current_city_index = 0
    if st.session_state.selected_city and st.session_state.selected_city in city_options:
        current_city_index = city_options.index(st.session_state.selected_city)

    with col_loc3:
        selected_city = st.selectbox("3. City:", options=city_options, index=current_city_index, key="city_selector", disabled=not selected_state or not st.session_state.cities)

    # Update selected city in session state immediately
    st.session_state.selected_city = selected_city


# --- Data Fetching Trigger & Display ---
st.divider()
col_btn, col_time_info = st.columns([1, 3]) # Button column + time display column

with col_btn:
    if st.button("Get Air Quality Data", key="get_aqi_button", use_container_width=True):
        final_country = st.session_state.selected_country
        final_state = st.session_state.selected_state
        final_city = st.session_state.selected_city

        if not user_api_key:
            st.error("❌ API key missing.")
            st.session_state.aqi_result = None
            st.session_state.last_api_fetch_time_utc = None # Reset fetch time
        elif not all([final_country, final_state, final_city]):
            st.warning("⚠️ Please select a Country, State/Region, and City.")
            st.session_state.aqi_result = None
            st.session_state.last_api_fetch_time_utc = None # Reset fetch time
        else:
            with st.spinner(f"Fetching data for {final_city}, {final_state}, {final_country}..."):
                result = get_iqair_detailed_data(final_city, final_state, final_country, user_api_key)
                st.session_state.aqi_result = result # Store result
                # Store the fetch time ONLY on success
                if result and result.get("status") == "success":
                    st.session_state.last_api_fetch_time_utc = result.get("fetch_timestamp_utc")
                    st.session_state.current_aqi_class = get_aqi_class(result.get("aqi_us"))
                else:
                    st.session_state.last_api_fetch_time_utc = None # Clear time on error
                    st.session_state.current_aqi_class = "aqi-unknown"
                # Rerun AFTER potentially updating state to ensure display refreshes
                st.rerun()


# Display Current Time and Last Update Time Info
with col_time_info:
    try:
        local_tz = pytz.timezone(YOUR_LOCAL_TIMEZONE)
        current_local_time = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S %Z")
        # **NEW: Clearer Label**
        st.caption(f"🕒 App's Current Time: {current_local_time}")
    except pytz.UnknownTimeZoneError:
        st.caption(f"⚠️ Invalid Timezone '{YOUR_LOCAL_TIMEZONE}'. Using UTC.")
        current_utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        st.caption(f"🕒 App's Current Time (UTC): {current_utc_time}")
    except Exception as e:
         st.caption(f"🕒 Error getting current time: {e}")

    # **NEW: Display API Fetch time**
    if st.session_state.last_api_fetch_time_utc:
        fetch_time_ago_str = time_ago(st.session_state.last_api_fetch_time_utc)
        st.caption(f"📶 Data fetched from API: {fetch_time_ago_str}")
    elif st.session_state.aqi_result and st.session_state.aqi_result.get("status") == "error":
         st.caption("📶 Data fetch failed.")
    # else: # No data fetched yet
        # st.caption("📶 Fetch data using the button.")


# --- Display Area ---
aqi_class_name = st.session_state.get('current_aqi_class', 'aqi-unknown')
# Use the CSS class on the main container for dynamic styling
st.markdown(f'<div class="content-wrapper {aqi_class_name}">', unsafe_allow_html=True)

if st.session_state.aqi_result:
    result = st.session_state.aqi_result
    if result and result.get("status") == "success":
        location_display = f"{result.get('city_returned', '')}, {result.get('state_returned', '')}, {result.get('country_returned', '')}"
        aqi_us = result.get("aqi_us")

        st.subheader(f"📊 Air Quality & Weather in {location_display}")
        # **NEW: Display Sensor Timestamp Clearly**
        sensor_time_str = result.get('timestamp_formatted', 'N/A')
        sensor_dt_utc = result.get('timestamp_utc')
        sensor_time_ago_str = time_ago(sensor_dt_utc) if sensor_dt_utc else "(unknown age)"
        st.caption(f"🌡️ Sensor Reading Timestamp: {sensor_time_str} ({sensor_time_ago_str})")

        # Note about potential differences
        st.info("""
            **Note:** Weather/AQI data is from IQAir API. Values (°C, AQI) & timestamps may differ from other sources
            (like Google) due to different measurement locations, update times, and methods.
            The 'Sensor Reading Timestamp' indicates when the measurement was recorded by the source.
            The 'Data fetched from API' indicates when this app retrieved the data.
            """, icon="ℹ️")

        col_gauge, col_health = st.columns([2, 3])

        with col_gauge:
            # --- AQI Gauge --- (as before)
            aqi_gauge_fig = create_aqi_gauge(aqi_us, st.session_state.theme)
            if aqi_gauge_fig:
                st.plotly_chart(aqi_gauge_fig, use_container_width=True)
            else:
                st.metric(label="Air Quality Index (US AQI)", value=f"{aqi_us if aqi_us is not None else 'N/A'}")

        with col_health:
             # --- Dynamic Health Recommendation Card (Revised Display) ---
             # Use a Streamlit container. Add a CSS class to style children if needed.
             with st.container(): # Removed border=True as we use CSS
                # Add a class via markdown IF complex styling needed beyond basic elements
                # st.markdown('<div class="health-card">', unsafe_allow_html=True)
                recommendation_text = get_dynamic_health_recommendation(result)
                # Render the markdown content generated by the function
                st.markdown(recommendation_text, unsafe_allow_html=True)
                # st.markdown('</div>', unsafe_allow_html=True) # Close div if using HTML injection

                # **Ensure CSS targets elements within this container appropriately**
                # e.g., in CSS: `.content-wrapper .stContainer .stMarkdown h3 { ... }`
                # Or add a specific class to the container's markdown if simpler methods fail


        st.divider()
        st.subheader("🌦️ Current Weather Conditions")
        # Weather Metrics (as before)
        col_w1, col_w2, col_w3, col_w4 = st.columns(4)
        with col_w1: st.metric(label="🌡️ Temperature", value=f"{result.get('temperature_c', 'N/A')} °C")
        with col_w2: st.metric(label="💧 Humidity", value=f"{result.get('humidity_percent', 'N/A')} %")
        with col_w3: st.metric(label="💨 Wind Speed", value=f"{result.get('wind_speed_mps', 'N/A')} m/s")
        with col_w4:
             wd = result.get('wind_direction_deg')
             wind_dir_str = f"{wd}°" if wd is not None else "N/A"
             st.metric(label="🧭 Wind Direction", value=wind_dir_str)

        # Pollutant Breakdown (Revised Display - Use Streamlit elements)
        if result.get("pollutants"):
            with st.container(): # Use container for grouping
                st.markdown('<div class="pollutant-details">', unsafe_allow_html=True) # Keep class for styling
                st.markdown("#### Specific Pollutant Concentrations")
                # Use columns or markdown for better layout than raw HTML <p>
                pollutant_cols = st.columns(2)
                col_idx = 0
                unit = " µg/m³" # Assume standard unit
                for name, value in result["pollutants"].items():
                    value_str = f"{value:.1f}" if isinstance(value, (int, float)) else str(value)
                    unit_str = unit if isinstance(value, (int, float)) else ''
                    with pollutant_cols[col_idx % 2]: # Alternate columns
                         st.markdown(f"**{name}:** `{value_str}{unit_str}`")
                    col_idx += 1
                st.markdown('</div>', unsafe_allow_html=True) # Close class div

    elif result and result.get("status") == "error":
        # Error message displayed by API function or button logic
        st.info("Failed to retrieve data. Check API key, network, or location selection.")
    # else: # No result yet

# --- AQI Level Explanation ---
# (Keep AQI expander as before)
with st.expander("What do the AQI levels mean?"):
    st.markdown("""
    The US Air Quality Index (AQI) is divided into categories:
    - **0-50 (Good - 🟢):** ...
    - **51-100 (Moderate - 🟡):** ...
    - **101-150 (Unhealthy for Sensitive Groups - 🟠):** ...
    - **151-200 (Unhealthy - 🔴):** ...
    - **201-300 (Very Unhealthy - 🟣):** ...
    - **301+ (Hazardous - 🟤):** ...
    """)

    # --- Conversational Agent Section (NEW) ---
    st.divider()
    st.subheader("🤖 Talk to AI Agent")
    # Ask user for the Agent URL (as requested)
    # Provide the specific URL you want as the default value
    default_agent_url = "https://elevenlabs.io/app/talk-to?agent_id=rHhQqxWxk4pue21ttj6s"
    user_provided_url = st.text_input(
        "Enter the ElevenLabs Agent URL:",
        value=st.session_state.get('agent_url', default_agent_url),  # Use default or stored value
        key="agent_url_input",
        help="Paste the URL for the ElevenLabs agent app (e.g., https://elevenlabs.io/app/talk-to?agent_id=...)"
    )

    # Update session state if input changes
    if user_provided_url != st.session_state.agent_url:
        st.session_state.agent_url = user_provided_url
        st.rerun()  # Rerun to reflect change immediately

    # Display the agent in an iframe if a valid URL is provided
    if st.session_state.agent_url:
        if "elevenlabs.io/app/talk-to" in st.session_state.agent_url:  # Basic check for validity
            st.markdown("Connect your microphone and interact with the agent below:")
            # Use a container to apply styling via CSS
            with st.container():
                st.markdown('<div class="agent-container">', unsafe_allow_html=True)
                try:
                    iframe(st.session_state.agent_url, height=600, scrolling=False)  # Adjust height as needed
                except Exception as e:
                    st.error(f"Could not load the agent iframe: {e}")
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.warning("Please enter a valid ElevenLabs Agent URL starting with 'https://elevenlabs.io/app/talk-to'.")
    else:
        st.info("Enter an ElevenLabs Agent URL above to load the conversational agent.")

st.markdown('</div>', unsafe_allow_html=True) # End content-wrapper div

# --- Footer ---
st.divider()
st.caption("App by MD MAHBUBUR RAHMAN for AI Olympiad Bangladesh 2025")