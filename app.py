import os
import json
import pickle
from datetime import datetime, timezone
import streamlit as st
from urllib.parse import urlencode
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from transformers import pipeline

# Allow insecure transport for local testing / Streamlit Cloud
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Load OAuth credentials
with open('credentials.json') as f:
    credentials_data = json.load(f)

redirect_uri = credentials_data['web']['redirect_uris'][0]
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Title
st.title("🗓 Google Calendar Reader with Transformers")
st.write(f"🔁 Redirect URI: {redirect_uri}")

# Helper: Create OAuth flow
def authenticate_web():
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return authorization_url, flow, state

# 1. Handle callback from Google
if 'code' in st.query_params and 'credentials' not in st.session_state:
    received_state = st.query_params.get('state')
    if os.path.exists('state_temp.json'):
        with open('state_temp.json', 'r') as f:
            stored_state = json.load(f).get('state')  # Corrected line
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
            st.error(f"❌ Authentication failed: {e}")
    else:
        st.error("⚠️ State mismatch! Possible CSRF attack.")

# 2. Try to load existing credentials
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

# 3. Show auth button if not authenticated
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

# 4. We're authenticated. Fetch and summarize events
creds = st.session_state.credentials
service = build('calendar', 'v3', credentials=creds)

# ➕ Get only today and future events
now = datetime.now(timezone.utc).isoformat()
events_result = service.events().list(
    calendarId='primary',
    timeMin=now,
    maxResults=10,
    singleEvents=True,
    orderBy='startTime'
).execute()

events = events_result.get('items', [])

if not events:
    st.write("📭 No upcoming events found.")
else:
    st.markdown("### 📅 Upcoming events:")
    event_texts = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        summary = event.get('summary', 'No Title')
        st.write(f"• **{start}**: {summary}")
        event_texts.append(f"{start}: {summary}")

    # ➕ Use smaller summarization model to avoid memory limits
    summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
    prompt = "Here are my upcoming events:\n" + "\n".join(event_texts)
    response = summarizer(prompt, max_length=50, min_length=25, do_sample=False)

    st.markdown("### ✨ Summary:")
    st.write(response[0]['summary_text'])
