import os
import json
import pickle
import streamlit as st
from datetime import datetime, timedelta
from urllib.parse import urlencode
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from transformers import pipeline

# Allow local insecure OAuth callback
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Load credentials
with open('credentials.json') as f:
    credentials_data = json.load(f)

redirect_uri = credentials_data['web']['redirect_uris'][0]
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Title
st.title("🗓 Google Calendar Reader with Transformers")
st.write(f"🔁 Redirect URI: {redirect_uri}")

# Helper: OAuth setup
def authenticate_web():
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    return authorization_url, flow, state

# 1. Handle callback
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

        query_string = urlencode(st.query_params, doseq=True)
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
        st.error("State mismatch! Possible CSRF.")

# 2. Load token from file
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

# 3. Prompt login if still unauthenticated
if 'credentials' not in st.session_state:
    authorization_url, flow, state = authenticate_web()
    with open('state_temp.json', 'w') as f:
        json.dump({'state': state}, f)

    st.markdown(f"""
        <a href="{authorization_url}">
            <button style="padding:10px;background:#0b8043;color:white;border:none;border-radius:5px;">
                🔐 Click here to authorize Google Calendar
            </button>
        </a>
    """, unsafe_allow_html=True)
    st.info("Please authorize access to your Google Calendar.")
    st.stop()

# 4. Fetch events
creds = st.session_state.credentials
service = build('calendar', 'v3', credentials=creds)

now = datetime.utcnow().isoformat() + 'Z'
tomorrow = (datetime.utcnow() + timedelta(days=2)).isoformat() + 'Z'

events_result = service.events().list(
    calendarId='primary',
    timeMin=datetime.utcnow().isoformat() + 'Z',
    timeMax=(datetime.utcnow() + timedelta(days=2)).isoformat() + 'Z',
    maxResults=50,
    singleEvents=True,
    orderBy='startTime'
).execute()

events = events_result.get('items', [])

# 5. Filter only today & tomorrow
today = datetime.utcnow().date()
tomorrow_date = today + timedelta(days=1)

filtered_events = []
event_texts = []

for event in events:
    start = event['start'].get('dateTime', event['start'].get('date'))
    summary = event.get('summary', 'No Title')

    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        if start_dt.date() in [today, tomorrow_date]:
            filtered_events.append((start_dt, summary))
            event_texts.append(f"{start_dt.strftime('%Y-%m-%d %H:%M')}: {summary}")
    except Exception as e:
        st.warning(f"Skipping malformed event: {e}")

# 6. Show events
if filtered_events:
    st.write("📅 **Upcoming events (Today & Tomorrow)**:")
    for dt, title in filtered_events:
        st.write(f"• {dt.strftime('%Y-%m-%d %H:%M')}: {title}")

    # Summarize with HuggingFace
    try:
        st.write("✨ **Summary:**")
        summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
        prompt = "Here are my upcoming events:\n" + "\n".join(event_texts)
        response = summarizer(prompt, max_length=50, min_length=25, do_sample=False)
        st.write(response[0]['summary_text'])
    except Exception as e:
        st.error(f"Error while summarizing: {e}")
else:
    st.info("No events for today or tomorrow.")
