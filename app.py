import streamlit as st
import json
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from datetime import datetime, timedelta
import pytz

# Load credentials from the credentials.json file
with open("credentials.json") as f:
    creds_data = json.load(f)

# Extract weather and news API keys from credentials.json
WEATHER_API_KEY = creds_data["WEATHER_API_KEY"]
NEWS_API_KEY = creds_data["NEWS_API_KEY"]

# List of cities in the format required
cities = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose",
    "Austin", "Jacksonville", "Fort Worth", "Columbus", "Indianapolis", "Charlotte", "San Francisco", "Seattle", "Denver", "Washington D.C.",
    "Boston", "El Paso", "Detroit", "Nashville", "Portland", "Memphis", "Oklahoma City", "Las Vegas", "Louisville", "Baltimore",
    "Milwaukee", "Albuquerque", "Tucson", "Fresno", "Mesa", "Sacramento", "Kansas City", "Long Beach", "Atlanta", "Raleigh",
    "Miami", "Omaha", "Cleveland", "Tulsa", "Minneapolis", "Arlington", "New Orleans", "Wichita", "Bakersfield", "Cincinnati"
]

# Function to get weather data
def get_weather(city):
    url = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={city}"
    try:
        response = requests.get(url)
        data = response.json()
        if 'error' in data:
            return f"Error: {data['error']['message']}"
        weather_info = data['current']
        return f"Weather in {city}: {weather_info['temp_c']}°C, {weather_info['condition']['text']}"
    except requests.exceptions.RequestException as e:
        return f"Error fetching weather: {e}"

# Function to get Google Calendar events
def get_calendar_events(credentials):
    service = build("calendar", "v3", credentials=credentials)
    now = datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
    events = service.events().list(calendarId='primary', timeMin=now, maxResults=10, singleEvents=True, orderBy='startTime').execute()
    return events.get('items', [])

# Function to authenticate with Google
def google_authenticate():
    credentials = None
    if st.session_state.get("credentials"):
        credentials = service_account.Credentials.from_service_account_info(st.session_state["credentials"])
    
    if not credentials or credentials.expired:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                scopes=["https://www.googleapis.com/auth/calendar.readonly"]
            )
            credentials = flow.run_local_server(port=0)
            st.session_state["credentials"] = credentials.to_json()
    return credentials

# Main app logic
def main():
    st.title("Agentic AI - Personal Assistant")

    # Step 1: Ask the user to choose a city for weather information
    city = st.selectbox("Choose your city for weather info:", cities)

    # Step 2: Google Calendar Authentication
    st.write("🔐 Please authorize access to your Google Calendar:")
    credentials = google_authenticate()

    # Fetch and display today's events
    events = get_calendar_events(credentials)
    if events:
        st.write("📅 Today's & Tomorrow's Events:")
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            start_dt = datetime.fromisoformat(start).astimezone(pytz.timezone('America/New_York'))
            if start_dt > datetime.now(pytz.timezone('America/New_York')):
                st.write(f"Event: {event['summary']}, Time: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        st.write("No upcoming events found.")

    # Step 3: Display Top News
    st.write("📰 Today's Top News:")
    news_url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"
    try:
        news_response = requests.get(news_url)
        news_data = news_response.json()
        if news_data["status"] == "ok":
            for article in news_data["articles"][:5]:
                st.write(f"• {article['title']} - {article['source']['name']}")
        else:
            st.write("Error fetching news.")
    except requests.exceptions.RequestException as e:
        st.write(f"Error fetching news: {e}")

    # Step 4: Display Weather Information
    st.write("🌤 Weather Information:")
    weather_info = get_weather(city)
    st.write(weather_info)

if __name__ == "__main__":
    main()
