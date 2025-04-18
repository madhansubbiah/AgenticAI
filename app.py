import os
import json
import pickle
import streamlit as st
from urllib.parse import urlencode
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from transformers import pipeline

# Allow insecure transport for local testing
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Load credentials
with open('credentials.json') as f:
    credentials_data = json.load(f)

redirect_uri = credentials_data['web']['redirect_uris'][0]
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# App Title
st.title("📅 Google Calendar Reader with Transformers")
st.write(f"Redirect URI: `{redirect_uri}`")

# Step 1 - Helper for OAuth URL
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

# Step 2 - Check if redirected from Google
query_params = st.query_params
if 'code' in query_params and 'credentials' not in st.session_state:
    code = query_params.get('code')
    state = query_params.get('state')

    # Load the expected state
    if os.path.exists("state_temp.json"):
        with open("state_temp.json") as f:
            saved_state = json.load(f).get("state")
        os.remove("state_temp.json")
    else:
        saved_state = None

    if saved_state == state:
        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )

        # Rebuild full URL
        full_redirect_url = f"{redirect_uri}?code={code}&state={state}"

        try:
            flow.fetch_token(authorization_response=full_redirect_url)
            creds = flow.credentials
            st.session_state.credentials = creds

            # Save token
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

            # Clear query and rerun
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ Auth Error: {e}")
    else:
        st.error("⚠️ Invalid state. Possible CSRF attack.")

# Step 3 - Try to load saved token
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

# Step 4 - Show Auth button
if 'credentials' not in st.session_state:
    auth_url, flow, state = authenticate_web()
    with open("state_temp.json", "w") as f:
        json.dump({"state": state}, f)

    st.markdown(
        f"""
        <div style="text-align:center;">
            <a href="{auth_url}" target="_self">
                <button style="padding: 0.75em 1.5em; font-size: 1rem; background-color: #0b8043; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    🔐 Click here to authorize Google Calendar
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.info("Please authorize Google Calendar access.")
    st.stop()

# Step 5 - You're authenticated. Fetch events
creds = st.session_state.credentials
service = build('calendar', 'v3', credentials=creds)

events_result = service.events().list(
    calendarId='primary',
    maxResults=10,
    singleEvents=True,
    orderBy='startTime'
).execute()

events = events_result.get('items', [])

if not events:
    st.write("📭 No upcoming events.")
else:
    st.subheader("📅 Upcoming Events:")
    event_texts = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        summary = event.get('summary', 'No Title')
        st.markdown(f"- **{start}** — {summary}")
        event_texts.append(f"{start}: {summary}")

    # Summarize
    st.write("🧠 Summarizing using Hugging Face Transformers...")
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    prompt = "Here are my upcoming events:\n" + "\n".join(event_texts)
    result = summarizer(prompt, max_length=60, min_length=25, do_sample=False)

    st.success("📋 Summary:")
    st.write(result[0]['summary_text'])
