import streamlit as st
import pandas as pd
import statistics
from datetime import datetime
from zoneinfo import ZoneInfo  # For time zone conversion
from amadeus import Client, ResponseError

st.set_page_config(layout="wide")

# A large list of airports (with codes and full names)
airports = [
    "ATL - Hartsfield-Jackson Atlanta International Airport",
    "LAX - Los Angeles International Airport",
    "ORD - O'Hare International Airport",
    "DFW - Dallas/Fort Worth International Airport",
    "DEN - Denver International Airport",
    "JFK - John F. Kennedy International Airport",
    "SFO - San Francisco International Airport",
    "SEA - Seattle-Tacoma International Airport",
    "MCO - Orlando International Airport",
    "LAS - McCarran International Airport",
    "PHX - Phoenix Sky Harbor International Airport",
    "MIA - Miami International Airport",
    "LGA - LaGuardia Airport",
    "BOS - Logan International Airport",
    "CDG - Charles de Gaulle Airport (Paris)",
    "LHR - London Heathrow Airport",
    "FRA - Frankfurt Airport",
    "DXB - Dubai International Airport",
    "HND - Tokyo Haneda Airport",
    "PEK - Beijing Capital International Airport",
    "SYD - Sydney Kingsford Smith Airport",
    "GRU - São Paulo–Guarulhos International Airport",
    "YYZ - Toronto Pearson International Airport",
    "AMS - Amsterdam Schiphol Airport",
    "ICN - Incheon International Airport",
    "SIN - Singapore Changi Airport",
    "MAD - Adolfo Suárez Madrid–Barajas Airport",
    "FCO - Leonardo da Vinci International Airport (Rome)",
    "MUC - Munich Airport",
    "IST - Istanbul Airport",
    "CPH - Copenhagen Airport",
    "BRU - Brussels Airport",
    "BOM - Chhatrapati Shivaji Maharaj International Airport (Mumbai)",
    "DEL - Indira Gandhi International Airport (Delhi)"
]

def get_airport_code(selection):
    return selection.split(" - ")[0]

carrier_mapping = {
    "AA": "American Airlines",
    "B6": "JetBlue Airways",
    "DL": "Delta Air Lines",
    "UA": "United Airlines",
    "WN": "Southwest Airlines",
    "AS": "Alaska Airlines",
    "NK": "Spirit Airlines",
    "F9": "Frontier Airlines",
    "OO": "SkyWest Airlines",
    "US": "US Airways",
    "AC": "Air Canada",
    "AF": "Air France",
    "BA": "British Airways",
    "LH": "Lufthansa",
    "KL": "KLM Royal Dutch Airlines",
    "IB": "Iberia",
    "AZ": "Alitalia",
    "SK": "Scandinavian Airlines",
    "LO": "LOT Polish Airlines",
    "LX": "SWISS International Air Lines",
    "SN": "Brussels Airlines",
    "EI": "Aer Lingus",
    "TP": "TAP Air Portugal",
    "OS": "Austrian Airlines",
    "CX": "Cathay Pacific",
    "CI": "China Airlines",
    "CZ": "China Southern Airlines",
    "CA": "Air China",
    "JL": "Japan Airlines",
    "NH": "All Nippon Airways",
    "KE": "Korean Air",
    "SQ": "Singapore Airlines",
    "MU": "China Eastern Airlines",
    "FM": "Shanghai Airlines",
    "EK": "Emirates",
    "QR": "Qatar Airways",
    "EY": "Etihad Airways",
    "ME": "Middle East Airlines",
    "QF": "Qantas",
    "VA": "Virgin Australia",
    "LA": "LATAM Airlines",
    "JJ": "LATAM Airlines Brasil",
    "AR": "Aerolíneas Argentinas",
    "SU": "Aeroflot",
    "TK": "Turkish Airlines",
    "U6": "Air Serbia",
    "UL": "SriLankan Airlines",
    "FJ": "Fiji Airways",
    "NZ": "Air New Zealand",
    "WS": "WestJet",
    "S7": "S7 Airlines",
    "G3": "Gol Transportes Aéreos"
}

def get_carrier_name(carrier_codes):
    unique_codes = list(dict.fromkeys(carrier_codes))
    mapped = [carrier_mapping.get(code, code) for code in unique_codes]
    return mapped[0] if len(mapped) == 1 else ", ".join(mapped)

cabin_priority = ['ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', 'FIRST']

def calculate_departure_penalty(departure_hour, ideal_hours, penalty_per_hr):
    return min([abs(departure_hour - ideal) * penalty_per_hr for ideal in ideal_hours])

def score_flight(flight, prefs):
    score = 0
    score += flight['layovers'] * prefs['layover_penalty']
    extra_duration = max(flight['total_duration'] - prefs['baseline_duration'], 0)
    score += extra_duration * prefs['duration_penalty_per_hr']
    dep_penalty = calculate_departure_penalty(
        flight['departure_time'], prefs['ideal_departure_times'], prefs['departure_penalty_per_hr']
    )
    score += dep_penalty
    allowed_cabin_index = cabin_priority.index(prefs['allowed_cabin'].upper())
    flight_cabin_index = cabin_priority.index(max(flight['cabins'], key=lambda c: cabin_priority.index(c)))
    if flight_cabin_index <= allowed_cabin_index:
        score += prefs['cabin_penalty'] * (allowed_cabin_index - flight_cabin_index)
    return score

def find_best_flight(flights, prefs):
    scored_flights = [(score_flight(f, prefs), f) for f in flights]
    scored_flights.sort(key=lambda x: x[0])
    return scored_flights[0]

# ------------------------
# UI - Flight Search Parameters
# ------------------------
st.title("Kickback")

# Four columns: Origin, Destination, Flight Date, and Adjustment Factor
col_origin, col_destination, col_date, col_adjust = st.columns(4)
with col_origin:
    origin_airport = st.selectbox("Select Origin", options=airports, index=1)
with col_destination:
    destination_airport = st.selectbox("Select Destination", options=airports, index=14)
with col_date:
    flight_date = st.date_input("Flight Date", value=datetime.today())
with col_adjust:
    adjustment_factor = st.slider("Reward Percentage", min_value=0, max_value=100, step=1, value=50)

origin_code = get_airport_code(origin_airport)
destination_code = get_airport_code(destination_airport)

# ------------------------
# Sidebar - Preferences
# ------------------------
st.sidebar.header("Preferences (Testing Only)")
allowed_cabin_pref = st.sidebar.selectbox("Allowed Cabin", options=cabin_priority, index=cabin_priority.index("FIRST"))
layover_penalty = st.sidebar.number_input("Layover Penalty", value=500, step=50)
duration_penalty_per_hr = st.sidebar.number_input("Duration Penalty per Hour", value=50, step=10)
baseline_duration = st.sidebar.number_input("Baseline Duration (hrs)", value=0, step=1)
ideal_departure_times = st.sidebar.multiselect("Ideal Departure Times (Hour of Day)", options=list(range(0, 24)), default=[8, 15])
departure_penalty_per_hr = st.sidebar.number_input("Departure Penalty per Hour", value=20, step=5)
cabin_penalty = st.sidebar.number_input("Cabin Penalty", value=500, step=50)

preferences = {
    'allowed_cabin': allowed_cabin_pref,
    'layover_penalty': layover_penalty,
    'duration_penalty_per_hr': duration_penalty_per_hr,
    'baseline_duration': baseline_duration,
    'ideal_departure_times': ideal_departure_times,
    'departure_penalty_per_hr': departure_penalty_per_hr,
    'cabin_penalty': cabin_penalty
}

# ------------------------
# Search Button & Caching Flight Data
# ------------------------
if st.button("Search Flights"):
    flight_data = []
    try:
        for cabin in cabin_priority:
            response = Client(
                client_id='0cjQ8qeGwWaX4rgmGOJQBjfUeglmB3Eb',
                client_secret='PZj9eYxASGYMGwFV'
            ).shopping.flight_offers_search.get(
                originLocationCode=origin_code,
                destinationLocationCode=destination_code,
                departureDate=flight_date.strftime("%Y-%m-%d"),
                adults=1,
                travelClass=cabin,
                max=20
            )
            for offer in response.data:
                price = float(offer['price']['grandTotal'])
                itinerary = offer['itineraries'][0]
                segments = itinerary['segments']
                departure_raw = segments[0]['departure']['at']
                arrival_raw = segments[-1]['arrival']['at']
                dep_time = datetime.fromisoformat(departure_raw).replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/New_York"))
                arr_time = datetime.fromisoformat(arrival_raw).replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/New_York"))
                layovers_count = len(segments) - 1

                cabins = []
                carriers = []
                for segment in segments:
                    seg_cabin = None
                    for tp in offer['travelerPricings']:
                        for fd in tp['fareDetailsBySegment']:
                            if fd['segmentId'] == segment['id']:
                                seg_cabin = fd['cabin']
                                break
                        if seg_cabin is not None:
                            break
                    cabins.append(seg_cabin)
                    carrier_code = segment.get('carrierCode', 'N/A')
                    carriers.append(carrier_code)
                
                unique_cabins = list(dict.fromkeys(cabins))
                cabin_str = unique_cabins[0] if len(unique_cabins) == 1 else ", ".join(unique_cabins)
                overall_carrier = get_carrier_name(carriers)
                
                if len(segments) > 1:
                    layover_locations = []
                    layover_times = []
                    for i in range(len(segments) - 1):
                        loc = segments[i]['arrival'].get('iataCode', 'N/A')
                        arrival_seg = datetime.fromisoformat(segments[i]['arrival']['at']).replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/New_York"))
                        next_departure_seg = datetime.fromisoformat(segments[i+1]['departure']['at']).replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/New_York"))
                        duration_hrs = (next_departure_seg - arrival_seg).total_seconds() / 3600
                        layover_locations.append(loc)
                        layover_times.append(round(duration_hrs, 2))
                    layover_locations_str = ", ".join(layover_locations)
                    layover_times_str = ", ".join(str(x) for x in layover_times)
                else:
                    layover_locations_str = ""
                    layover_times_str = ""
                
                total_duration = (arr_time - dep_time).total_seconds() / 3600
                departure_hour = dep_time.hour

                flight_data.append({
                    'price': price,
                    'departure_time': departure_hour,
                    'total_duration': total_duration,
                    'layovers': layovers_count,
                    'cabins': cabins,
                    'cabin': cabin_str,
                    'carrier': overall_carrier,
                    'departure': dep_time.isoformat(),
                    'arrival': arr_time.isoformat(),
                    'layover_locations': layover_locations_str,
                    'layover_times': layover_times_str
                })
    except ResponseError as error:
        st.error(f"Error fetching flights: {error}")
    
    # Cache flight_data in session_state
    st.session_state.flight_data = flight_data

# ------------------------
# Display Table Using Cached Data
# ------------------------
if "flight_data" in st.session_state:
    flight_data = st.session_state.flight_data
    # Determine the best flight (for reward calculation)
    best_flight_score, best_flight = find_best_flight(flight_data, preferences)
    best_price = best_flight['price']
    
    # Recalculate reward with adjustment_factor without calling API again
    rows = []
    for flight in flight_data:
        dep_time_str = datetime.fromisoformat(flight['departure']).strftime("%I:%M %p")
        arr_time_str = datetime.fromisoformat(flight['arrival']).strftime("%I:%M %p")
        duration_val = round(flight['total_duration'], 2)
        # Original reward = best_price - flight price, then adjusted:
        adjustment_factor_absolute = adjustment_factor / 100.0
        adjusted_reward = round((best_price - flight['price']) * adjustment_factor_absolute, 2)
        savings = best_price - flight['price'] - adjusted_reward
        rows.append({
            "Carrier": flight['carrier'],
            "Cabin": flight['cabin'],
            "Price": flight['price'],
            "Duration (hrs)": duration_val,
            "Departure (ET)": dep_time_str,
            "Arrival (ET)": arr_time_str,
            "Layovers": flight['layovers'],
            "Kickback": adjusted_reward,
            "Business Savings": savings,
            "Layover Locations": flight['layover_locations'],
            "Layover Times (hrs)": flight['layover_times']
        })
    
    df_table = pd.DataFrame(rows)
    st.subheader("Flight Results")
    st.dataframe(df_table, height=300)
