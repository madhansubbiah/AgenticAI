import streamlit as st
import os
import datetime
import pickle
import json
from transformers import pipeline
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# Set up page
st.set_page_config(page_title="Google Calendar Reader with Transformers")
st.title("🗓 Google Calendar Reader with Transformers")

st.markdown("🔁 Redirect URI: https://my-agentic-ai.streamlit.app")

# Use Streamlit's new query_params
query_params = st.query_params

# Step 1: Google OAuth2 Authentication
CLIENT_SECRET_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CREDENTIALS_PICKLE = 'token.pkl'

def save_credentials_to_pickle(creds):
    with open(CREDENTIALS_PICKLE, 'wb') as token:
        pickle.dump(creds, token)

def load_credentials_from_pickle():
    if os.path.exists(CREDENTIALS_PICKLE):
        with open(CREDENTIALS_PICKLE, 'rb') as token:
            return pickle.load(token)
    return None

creds = load_credentials_from_pickle()

# Auth flow
if not creds:
    if 'code' not in query_params:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri='https://my-agentic-ai.streamlit.app'
        )
        auth_url, _ = flow.authorization_url(prompt='consent')
        st.markdown(f"🔐 [Click here to authorize Google Calendar]({auth_url})")
        st.stop()
    else:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri='https://my-agentic-ai.streamlit.app'
        )
        flow.fetch_token(code=query_params['code'])
        creds = flow.credentials
        save_credentials_to_pickle(creds)
        st.rerun()

# Calendar API
service = build('calendar', 'v3', credentials=creds)

# Calculate today and tomorrow's start and end times
tz_offset = datetime.timedelta(hours=0)  # use UTC
now = datetime.datetime.utcnow()

today_start = datetime.datetime.combine(now.date(), datetime.time.min)
today_end = datetime.datetime.combine(now.date(), datetime.time.max)

tomorrow = now.date() + datetime.timedelta(days=1)
tomorrow_start = datetime.datetime.combine(tomorrow, datetime.time.min)
tomorrow_end = datetime.datetime.combine(tomorrow, datetime.time.max)

# Fetch events between today_start and tomorrow_end
events_result = service.events().list(
    calendarId='primary',
    timeMin=today_start.isoformat() + 'Z',
    timeMax=tomorrow_end.isoformat() + 'Z',
    singleEvents=True,
    orderBy='startTime'
).execute()

events = events_result.get('items', [])

# Filter to only today and tomorrow
today_events = []
tomorrow_events = []

for event in events:
    start = event['start'].get('dateTime', event['start'].get('date'))
    start_dt = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
    summary = event.get('summary', 'No Title')

    if today_start <= start_dt <= today_end:
        today_events.append(f"{start}: {summary}")
    elif tomorrow_start <= start_dt <= tomorrow_end:
        tomorrow_events.append(f"{start}: {summary}")

st.success("✅ Successfully authenticated!")

# Show today's events
st.subheader("📅 Today's Events:")
if today_events:
    for event in today_events:
        st.write(f"• {event}")
else:
    st.write("No events found for today.")

# Show tomorrow's events
st.subheader("📅 Tomorrow's Events:")
if tomorrow_events:
    for event in tomorrow_events:
        st.write(f"• {event}")
else:
    st.write("No events found for tomorrow.")

# Optional summary using transformers
combined_text = " ".join(today_events + tomorrow_events)

if combined_text:
    try:
        summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
        summary = summarizer(combined_text, max_length=100, min_length=25, do_sample=False)[0]['summary_text']
        st.subheader("✨ Summary:")
        st.write(summary)
    except Exception as e:
        st.error(f"Error in summarization: {e}")
