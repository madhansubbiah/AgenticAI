import streamlit as st
import json
import requests
from datetime import datetime, timedelta
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build
from langgraph.graph import StateGraph

# Load credentials
with open("credentials.json") as f:
    creds_data = json.load(f)

google_creds = service_account.Credentials.from_service_account_info(
    creds_data,
    scopes=["https://www.googleapis.com/auth/calendar.readonly"]
)

weather_api_key = creds_data.get("weather_api_key")
news_api_key = creds_data.get("news_api_key")

# --- UI ---
st.title("🧠 AI Smart Daily Dashboard")
cities = ["New York", "San Francisco", "Chicago", "Houston", "Miami", "Los Angeles", "Seattle", "Dallas", "Boston", "Denver"]
city = st.selectbox("Choose your city to get the weather report:", cities)

# --- STATE MANAGEMENT FOR LANGGRAPH ---
class AppState(dict):
    pass

# --- NODES ---
def fetch_events(state):
    try:
        service = build("calendar", "v3", credentials=google_creds)
        now = datetime.utcnow().isoformat() + 'Z'
        tomorrow = (datetime.utcnow() + timedelta(days=2)).isoformat() + 'Z'

        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            timeMax=tomorrow,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        today = datetime.utcnow().date()
        tomorrow_date = today + timedelta(days=1)

        today_events = []
        tomorrow_events = []

        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            try:
                start_dt = datetime.fromisoformat(start)
            except:
                start_dt = datetime.strptime(start, "%Y-%m-%d")

            if start_dt.date() == today:
                today_events.append(event['summary'])
            elif start_dt.date() == tomorrow_date:
                tomorrow_events.append(event['summary'])

        state["today_events"] = today_events
        state["tomorrow_events"] = tomorrow_events
    except Exception as e:
        state["calendar_error"] = str(e)

    return state

def fetch_news(state):
    try:
        url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={news_api_key}"
        response = requests.get(url)
        data = response.json()

        articles = data.get("articles", [])[:5]
        news_titles = [f"• {article['title']} - {article['source']['name']}" for article in articles]
        state["news"] = news_titles
    except Exception as e:
        state["news_error"] = str(e)

    return state

def fetch_weather(state):
    city = state.get("city")
    try:
        url = f"http://api.weatherapi.com/v1/current.json?key={weather_api_key}&q={city}"
        response = requests.get(url)
        data = response.json()

        condition = data["current"]["condition"]["text"]
        temp_c = data["current"]["temp_c"]
        feelslike_c = data["current"]["feelslike_c"]

        state["weather"] = f"{condition}, {temp_c}°C (Feels like {feelslike_c}°C)"
    except:
        state["weather"] = f"Could not fetch weather data for {city}. Please try again."

    return state

def display_results(state):
    st.subheader("📅 Today's & Tomorrow's Events")
    if state.get("calendar_error"):
        st.error("Calendar error: " + state["calendar_error"])
    else:
        st.write("**Today:**")
        if state.get("today_events"):
            for ev in state["today_events"]:
                st.write(f"- {ev}")
        else:
            st.write("No events for today.")

        st.write("**Tomorrow:**")
        if state.get("tomorrow_events"):
            for ev in state["tomorrow_events"]:
                st.write(f"- {ev}")
        else:
            st.write("No events for tomorrow.")

    st.subheader("📰 Today's Top News")
    if state.get("news_error"):
        st.error("News error: " + state["news_error"])
    else:
        for headline in state.get("news", []):
            st.write(headline)

    st.subheader(f"☀️ Weather in {state['city']}")
    st.write(state.get("weather", "No weather data available."))

    return state

# --- BUILD LANGGRAPH ---
graph = StateGraph(AppState)
graph.add_node("fetch_events", fetch_events)
graph.add_node("fetch_news", fetch_news)
graph.add_node("fetch_weather", fetch_weather)
graph.add_node("display_results", display_results)

# Order of flow
graph.set_entry_point("fetch_events")
graph.add_edge("fetch_events", "fetch_news")
graph.add_edge("fetch_news", "fetch_weather")
graph.add_edge("fetch_weather", "display_results")

app = graph.compile()

# --- Run Graph ---
initial_state = AppState({"city": city})
app.invoke(initial_state)
