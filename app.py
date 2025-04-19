import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pytz
import json
import requests
from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

# ---- Load credentials ----
with open("credentials.json") as f:
    secrets = json.load(f)

client_config = {
    "web": secrets["web"]
}
NEWS_API_KEY = secrets["NEWS_API_KEY"]
WEATHER_API_KEY = secrets["WEATHER_API_KEY"]

# ---- City Selection (Dropdown - UI) ----
cities = ["New York", "San Francisco", "Chicago", "Houston", "Miami", "Los Angeles", "Seattle", "Dallas", "Boston", "Denver"]
selected_city = st.selectbox("Choose your city for weather info:", cities)

# ---- Google Auth ----
if "credentials" not in st.session_state:
    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        redirect_uri="https://my-agentic-ai.streamlit.app"
    )

    auth_url, _ = flow.authorization_url(prompt="consent")
    st.write("### 🔐 Please authorize access to your Google Calendar:")
    st.markdown(f"[Authorize]({auth_url})")
    st.stop()

# ---- Events Display Logic ----
def fetch_calendar_events(credentials):
    service = build("calendar", "v3", credentials=credentials)

    now = datetime.utcnow().isoformat() + "Z"
    tomorrow = (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z"

    events_result = service.events().list(
        calendarId='primary', timeMin=now, timeMax=tomorrow,
        singleEvents=True, orderBy='startTime').execute()
    
    events = events_result.get('items', [])
    event_text = "📅 **Today's & Tomorrow's Events**\n"
    if not events:
        event_text += "No upcoming events found."
    else:
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            local_start = start_dt.astimezone(pytz.timezone("America/New_York"))
            summary = event.get("summary", "No Title")
            event_text += f"- {local_start.strftime('%Y-%m-%d %I:%M %p')}: {summary}\n"
    return event_text

# ---- News Logic ----
def fetch_top_news():
    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        news_data = response.json()
        articles = news_data["articles"][:5]
        news_text = "📰 **Today's Top News**\n"
        for article in articles:
            news_text += f"- {article['title']} - {article['source']['name']}\n"
        return news_text
    return "Failed to fetch news."

# ---- Weather Logic ----
def fetch_weather(city):
    url = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={city}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        temp_c = data['current']['temp_c']
        condition = data['current']['condition']['text']
        return f"🌤️ **Weather in {city}:** {temp_c}°C, {condition}"
    else:
        return f"Could not fetch weather data for {city}. Please try again."

# ---- LangGraph Integration ----
def create_graph():
    def calendar_node(state):
        return {"calendar": fetch_calendar_events(st.session_state.credentials)}

    def news_node(state):
        return {"news": fetch_top_news()}

    def weather_node(state):
        return {"weather": fetch_weather(selected_city)}

    builder = StateGraph()
    builder.add_node("calendar", RunnableLambda(calendar_node))
    builder.add_node("news", RunnableLambda(news_node))
    builder.add_node("weather", RunnableLambda(weather_node))

    builder.set_entry_point("calendar")
    builder.add_edge("calendar", "news")
    builder.add_edge("news", "weather")
    builder.add_edge("weather", END)

    graph = builder.compile()
    return graph

# ---- Run LangGraph ----
graph = create_graph()
result = graph.invoke({}, config=RunnableConfig())

# ---- Display in order ----
st.markdown(result["calendar"])
st.markdown(result["news"])
st.markdown(result["weather"])
