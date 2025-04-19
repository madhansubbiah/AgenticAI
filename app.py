import os
import json
import pickle
import requests
import streamlit as st
from datetime import datetime, timedelta
from urllib.parse import urlencode
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from transformers import pipeline
import pytz

# Setup
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
with open('credentials.json') as f:
    credentials_data = json.load(f)

redirect_uri = credentials_data['web']['redirect_uris'][0]
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
NEWS_API_KEY = credentials_data.get('NEWS_API_KEY', '')
WEATHER_API_KEY = credentials_data.get('WEATHER_API_KEY', '')
CITIES = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose"]

st.title("🧠 AI Daily Assistant")
st.write(f"🔁 Redirect URI: {redirect_uri}")

# Auth helper
def authenticate_web():
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    return authorization_url, flow, state

# OAuth Callback
if 'code' in st.query_params and 'credentials' not in st.session_state:
    received_state = st.query_params.get('state')
    if os.path.exists('state_temp.json'):
        with open('state_temp.json', 'r') as f:
            stored_state = json.load(f).get('state')
        os.remove('state_temp.json')
    else:
        stored_state = None

    if stored_state == received_state:
        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        query_dict = st.query_params
        query_string = urlencode(query_dict, doseq=True)
        authorization_response = f"{redirect_uri}?{query_string}"

        try:
            flow.fetch_token(authorization_response=authorization_response)
            creds = flow.credentials
            st.session_state.credentials = creds
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
            st.success("✅ Successfully authenticated!")
        except Exception as e:
            st.error(f"Authentication failed: {e}")
    else:
        st.error("State mismatch! Possible CSRF attack.")

# Load credentials if available
if 'credentials' not in st.session_state:
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
        if creds and creds.valid:
            st.session_state.credentials = creds
        elif creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            st.session_state.credentials = creds
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

# Prompt for login if not authenticated
if 'credentials' not in st.session_state:
    authorization_url, flow, state = authenticate_web()
    with open('state_temp.json', 'w') as f:
        json.dump({'state': state}, f)

    st.markdown(
        f"""
        <div style="text-align:center;">
            <a href="{authorization_url}" target="_self">
                <button style="padding: 0.75em 1.5em; font-size: 1rem; background-color: #0b8043; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    🔐 Click here to authorize Google Calendar
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.info("Please authorize access to your Google Calendar.")
    st.stop()

# -------- Calendar Section --------
creds = st.session_state.credentials
service = build('calendar', 'v3', credentials=creds)

utc = pytz.UTC
now = datetime.utcnow().replace(tzinfo=utc)
today_start = datetime(now.year, now.month, now.day, tzinfo=utc)
tomorrow_end = today_start + timedelta(days=2)

events_result = service.events().list(
    calendarId='primary',
    timeMin=today_start.isoformat(),
    timeMax=tomorrow_end.isoformat(),
    singleEvents=True,
    orderBy='startTime'
).execute()

events = events_result.get('items', [])

st.subheader("📅 Today's & Tomorrow's Events")
event_texts = []
for event in events:
    start = event['start'].get('dateTime', event['start'].get('date'))
    summary = event.get('summary', 'No Title')
    start_dt = datetime.fromisoformat(start)
    if start_dt.tzinfo is None:
        start_dt = utc.localize(start_dt)

    if today_start <= start_dt <= tomorrow_end:
        st.write(f"• {start_dt}: {summary}")
        event_texts.append(f"{start_dt}: {summary}")

# Summarize events
if event_texts:
    st.subheader("✨ Calendar Summary")
    summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
    event_summary = summarizer(" ".join(event_texts), max_length=60, min_length=25, do_sample=False)
    st.write(event_summary[0]['summary_text'])
else:
    st.write("No events for today and tomorrow.")

# -------- News Section --------
st.subheader("📰 Today's Top News")
news_url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"
response = requests.get(news_url)
news_data = response.json()

articles = news_data.get('articles', [])[:5]
news_texts = []

if not articles:
    st.warning("No news articles found.")
else:
    for article in articles:
        st.markdown(f"**• {article['title']}**")
        news_texts.append(article['title'] + ". " + (article.get('description') or ''))

    if news_texts:
        st.subheader("🧠 News Summary")
        full_news = " ".join(news_texts)
        news_summary = summarizer(full_news, max_length=60, min_length=25, do_sample=False)
        st.write(news_summary[0]['summary_text'])

# -------- Weather Section (after everything else) --------
st.subheader("🌦 Check Weather Info")
selected_city = st.selectbox('Select a city to view its weather:', CITIES)

if selected_city:
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={selected_city}&appid={WEATHER_API_KEY}&units=metric"
    weather_response = requests.get(weather_url)
    weather_data = weather_response.json()

    if weather_data.get('cod') != 200:
        st.warning(f"Could not fetch weather data for {selected_city}.")
        st.write(f"Error: {weather_data.get('message')}")
    else:
        st.subheader(f"🌤 Weather in {selected_city}")
        temp = weather_data['main']['temp']
        weather_desc = weather_data['weather'][0]['description']
        humidity = weather_data['main']['humidity']
        wind_speed = weather_data['wind']['speed']

        st.write(f"Temperature: {temp}°C")
        st.write(f"Weather: {weather_desc.capitalize()}")
        st.write(f"Humidity: {humidity}%")
        st.write(f"Wind Speed: {wind_speed} m/s")
