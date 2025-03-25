import streamlit as st
import pandas as pd
import statistics
from datetime import datetime
from amadeus import Client, ResponseError

# Set the page to wide mode so content fills the page
st.set_page_config(layout="wide")

# A comprehensive carrier mapping dictionary.
carrier_mapping = {
    # U.S. carriers
    "AA": "American Airlines",
    "B6": "JetBlue Airways",
    "DL": "Delta Air Lines",
    "UA": "United Airlines",
    "WN": "Southwest Airlines",
    "AS": "Alaska Airlines",
    "NK": "Spirit Airlines",
    "F9": "Frontier Airlines",
    "OO": "SkyWest Airlines",
    "US": "US Airways",  # Historical; now merged with American Airlines

    # Canadian carriers
    "AC": "Air Canada",

    # European carriers
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

    # Asian carriers
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

    # Middle Eastern carriers
    "EK": "Emirates",
    "QR": "Qatar Airways",
    "EY": "Etihad Airways",
    "ME": "Middle East Airlines",

    # Oceania carriers
    "QF": "Qantas",
    "VA": "Virgin Australia",

    # Latin American carriers
    "LA": "LATAM Airlines",
    "JJ": "LATAM Airlines Brasil",
    "AR": "Aerolíneas Argentinas",

    # Other major international carriers
    "SU": "Aeroflot",
    "TK": "Turkish Airlines",
    "U6": "Air Serbia",
    "UL": "SriLankan Airlines",
    "FJ": "Fiji Airways",
    "NZ": "Air New Zealand",
    "WS": "WestJet",
    "S7": "S7 Airlines",
    "G3": "Gol Transportes Aéreos"
    # Add more mappings as needed.
}

def get_carrier_name(carrier_codes):
    """
    Given a list of carrier codes, convert each to its full name (if known)
    and return a single string. If all segments use the same carrier, return
    that name; otherwise, return a comma-separated list of unique names.
    """
    unique_codes = list(dict.fromkeys(carrier_codes))
    mapped = [carrier_mapping.get(code, code) for code in unique_codes]
    if len(mapped) == 1:
        return mapped[0]
    else:
        return ", ".join(mapped)

# Define cabin priority (from lowest to highest)
cabin_priority = ['ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', 'FIRST']

def calculate_departure_penalty(departure_hour, ideal_hours, penalty_per_hr):
    penalties = [abs(departure_hour - ideal) * penalty_per_hr for ideal in ideal_hours]
    return min(penalties)

def score_flight(flight, prefs):
    score = 0
    # Penalize layovers
    score += flight['layovers'] * prefs['layover_penalty']
    # Penalize extra duration beyond baseline
    extra_duration = max(flight['total_duration'] - prefs['baseline_duration'], 0)
    score += extra_duration * prefs['duration_penalty_per_hr']
    # Smooth departure time penalty
    dep_penalty = calculate_departure_penalty(
        flight['departure_time'], prefs['ideal_departure_times'], prefs['departure_penalty_per_hr']
    )
    score += dep_penalty
    # Cabin penalty (if flight's cabin is lower than allowed)
    allowed_cabin_index = cabin_priority.index(prefs['allowed_cabin'].upper())
    # Note: We no longer use a single overall cabin value here.
    # For scoring, we could use the best cabin per our priority:
    flight_cabin_index = cabin_priority.index(max(flight['cabins'], key=lambda c: cabin_priority.index(c)))
    if flight_cabin_index <= allowed_cabin_index:
        score += prefs['cabin_penalty'] * (allowed_cabin_index - flight_cabin_index)
    return score

def find_best_flight(flights, prefs):
    scored_flights = []
    for flight in flights:
        flight_score = score_flight(flight, prefs)
        scored_flights.append((flight_score, flight))
    scored_flights.sort(key=lambda x: x[0])
    return scored_flights[0]  # Returns tuple (score, flight)

# --- Streamlit UI ---
st.title("Flight Finder App")

# Layout: Flight Search and Preferences side by side
col1, col2 = st.columns(2)

with col1:
    st.header("Flight Search Parameters")
    origin = st.text_input("Origin Airport Code", "LGA")
    destination = st.text_input("Destination Airport Code", "SFO")
    departure_date = st.date_input("Departure Date")

with col2:
    st.markdown(
        '<div style="background-color:#ffcccc; padding: 10px; border-radius: 5px;">'
        '<strong>Testing Preferences:</strong> (For testing purposes only)'
        '</div>',
        unsafe_allow_html=True,
    )
    allowed_cabin_pref = st.selectbox("Allowed Cabin", options=cabin_priority, index=cabin_priority.index("FIRST"))
    layover_penalty = st.number_input("Layover Penalty", value=500, step=50)
    duration_penalty_per_hr = st.number_input("Duration Penalty per Hour", value=50, step=10)
    baseline_duration = st.number_input("Baseline Duration (hrs)", value=0, step=1)
    ideal_departure_times = st.multiselect("Ideal Departure Times (Hour of Day)", options=list(range(0, 24)), default=[8, 15])
    departure_penalty_per_hr = st.number_input("Departure Penalty per Hour", value=20, step=5)
    cabin_penalty = st.number_input("Cabin Penalty", value=500, step=50)

preferences = {
    'allowed_cabin': allowed_cabin_pref,
    'layover_penalty': layover_penalty,
    'duration_penalty_per_hr': duration_penalty_per_hr,
    'baseline_duration': baseline_duration,
    'ideal_departure_times': ideal_departure_times,
    'departure_penalty_per_hr': departure_penalty_per_hr,
    'cabin_penalty': cabin_penalty
}

search_submitted = st.button("Search Flights")

if search_submitted:
    # Initialize Amadeus client (replace with your actual API credentials)
    amadeus = Client(
        client_id='0cjQ8qeGwWaX4rgmGOJQBjfUeglmB3Eb',
        client_secret='PZj9eYxASGYMGwFV'
    )
    
    flight_data = []
    # Loop through all cabin classes to fetch flight offers
    for cabin in cabin_priority:
        try:
            response = amadeus.shopping.flight_offers_search.get(
                originLocationCode=origin,
                destinationLocationCode=destination,
                departureDate=departure_date.strftime("%Y-%m-%d"),
                adults=1,
                travelClass=cabin,
                max=20
            )
            flight_offers = response.data
            for offer in flight_offers:
                price = float(offer['price']['grandTotal'])
                itinerary = offer['itineraries'][0]
                segments = itinerary['segments']
                departure = segments[0]['departure']['at']
                arrival = segments[-1]['arrival']['at']
                layovers_count = len(segments) - 1

                # For each segment, collect cabin and carrier info.
                cabins = []
                carriers = []
                for segment in segments:
                    seg_cabin = None
                    for traveler_pricing in offer['travelerPricings']:
                        for fare_detail in traveler_pricing['fareDetailsBySegment']:
                            if fare_detail['segmentId'] == segment['id']:
                                seg_cabin = fare_detail['cabin']
                                break
                        if seg_cabin is not None:
                            break
                    cabins.append(seg_cabin)
                    carrier_code = segment.get('carrierCode', 'N/A')
                    carriers.append(carrier_code)
                
                # Compute unique cabin string (if all same, show one; otherwise list unique values)
                unique_cabins = list(dict.fromkeys(cabins))
                cabin_str = unique_cabins[0] if len(unique_cabins) == 1 else ", ".join(unique_cabins)
                
                # Compute overall carrier string from carriers using full names
                overall_carrier = get_carrier_name(carriers)
                
                # Compute layover locations and times if there are multiple segments.
                if len(segments) > 1:
                    layover_locations = []
                    layover_times = []
                    for i in range(len(segments) - 1):
                        # Use arrival iataCode as layover location, if available.
                        loc = segments[i]['arrival'].get('iataCode', 'N/A')
                        arrival_time = datetime.fromisoformat(segments[i]['arrival']['at'])
                        next_departure_time = datetime.fromisoformat(segments[i+1]['departure']['at'])
                        layover_duration = (next_departure_time - arrival_time).total_seconds() / 3600
                        layover_locations.append(loc)
                        layover_times.append(round(layover_duration, 2))
                    layover_locations_str = ", ".join(layover_locations)
                    layover_times_str = ", ".join(str(x) for x in layover_times)
                else:
                    layover_locations_str = ""
                    layover_times_str = ""
                
                dep_time = datetime.fromisoformat(departure)
                arr_time = datetime.fromisoformat(arrival)
                total_duration = (arr_time - dep_time).total_seconds() / 3600
                departure_hour = dep_time.hour
                
                # Save extra info (also keep cabins for scoring purposes)
                flight_data.append({
                    'price': price,
                    'departure_time': departure_hour,
                    'total_duration': total_duration,
                    'layovers': layovers_count,
                    'cabins': cabins,  # For scoring purposes
                    'cabin': cabin_str,  # For display
                    'carrier': overall_carrier,
                    'departure': departure,
                    'arrival': arrival,
                    'layover_locations': layover_locations_str,
                    'layover_times': layover_times_str
                })
        except ResponseError as error:
            st.error(f"Error fetching flights for cabin {cabin}: {error}")
    
    if flight_data:
        # Determine the baseline flight (used for reward calculation)
        best_flight_score, best_flight = find_best_flight(flight_data, preferences)
        best_price = best_flight['price']

        # Build the concise table data.
        discreet_rows = []
        for flight in flight_data:
            dep_time_str = datetime.fromisoformat(flight['departure']).strftime("%I:%M %p")
            arr_time_str = datetime.fromisoformat(flight['arrival']).strftime("%I:%M %p")
            duration_val = round(flight['total_duration'], 2)
            reward_val = round(best_price - flight['price'], 2)
            discreet_rows.append({
                "Carrier": flight['carrier'],         # Full carrier name(s)
                "Cabin": flight['cabin'],               # Cabin(s) per leg
                "Price": flight['price'],               # Numeric value
                "Duration (hrs)": duration_val,         # Numeric value
                "Departure": dep_time_str,
                "Arrival": arr_time_str,
                "Layovers": flight['layovers'],         # Numeric value
                "Reward": reward_val,                   # Numeric value
                "Layover Locations": flight['layover_locations'],
                "Layover Times (hrs)": flight['layover_times']
            })
        
        df_table = pd.DataFrame(discreet_rows)
        st.subheader("Flight Results")
        st.dataframe(df_table, height=300)
    else:
        st.info("No flight data available.")
