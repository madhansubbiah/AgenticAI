import os
import streamlit as st
import requests
import time
from langgraph.graph import StateGraph, END
from typing import TypedDict
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
import pickle
import datetime

# Load secrets
API_TOKEN = st.secrets["general"]["HUGGINGFACE_API_KEY"]
APP_URL = st.secrets["general"]["STREAMLIT_APP_URL"]
ENV = st.secrets["general"].get("STREAMLIT_ENV", "development")
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

st.write("🔧 Environment:", ENV)
st.write("🔧 App URL:", APP_URL)

# TypedDict for LangGraph state
class SummaryState(TypedDict):
    text: str
    summary: str

# Summarization logic
def summarize_text(state: SummaryState) -> SummaryState:
    text = state["text"]
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    payload = {"inputs": text}

    for attempt in range(3):
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            summary = response.json()[0]["summary_text"]
            return {"text": text, "summary": summary}
        elif response.status_code == 503:
            st.warning(f"Summarization temporarily unavailable. Retrying in 2s... (Attempt {attempt+1}/3)")
            time.sleep(2)
        else:
            st.error(f"Summarization error: {response.status_code} - {response.text}")
            return {"text": text, "summary": f"Error: {response.text}"}

    return {"text": text, "summary": "Service unavailable after retries."}

# LangGraph pipeline setup
def create_langgraph_pipeline():
    builder = StateGraph(SummaryState)
    builder.add_node("summarize", summarize_text)
    builder.set_entry_point("summarize")
    builder.set_finish_point("summarize")
    return builder.compile()

# Get Google OAuth URL
def get_google_auth_url():
    redirect_uri = APP_URL if ENV == "production" else "http://localhost:8501/"
    st.write("🔗 Using redirect URI:", redirect_uri)

    if not os.path.exists("credentials.json"):
        st.error("Missing credentials.json in project directory.")
        return None

    try:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        flow.redirect_uri = redirect_uri
        auth_url, _ = flow.authorization_url(access_type="offline", prompt='consent', include_granted_scopes="true")
        st.session_state['oauth_flow'] = flow
        return auth_url
    except Exception as e:
        st.error(f"OAuth Flow Error: {e}")
        return None

# Build Calendar API service
def get_calendar_service(credentials):
    try:
        return build("calendar", "v3", credentials=credentials)
    except Exception as e:
        st.error(f"Google Calendar service build error: {e}")
        raise

# Fetch Google Calendar Events
def get_google_calendar_events(credentials):
    try:
        service = get_calendar_service(credentials)
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        st.write(f"Fetching events from: {now}")

        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        st.write(f"Found {len(events)} events.")

        if not events:
            return "No upcoming events found."

        events_str = "Upcoming events:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            events_str += f"- {event.get('summary', 'No Title')} ({start})\n"

        return events_str

    except RefreshError:
        st.error("🔒 Authentication expired. Please re-authorize.")
        if os.path.exists("token.pickle"):
            os.remove("token.pickle")
            st.info("Deleted old token.")
        if 'credentials' in st.session_state:
            del st.session_state['credentials']
        raise
    except Exception as e:
        st.error(f"❌ Error fetching calendar events: {e}")
        raise

# ---------------- Streamlit UI ---------------- #

st.title("📅 Calendar + 📝 Text Summarizer with LangGraph")

# Init session state
if 'credentials' not in st.session_state:
    st.session_state.credentials = None
if 'oauth_flow' not in st.session_state:
    st.session_state.oauth_flow = None

# Load saved credentials
if not st.session_state.credentials and os.path.exists("token.pickle"):
    try:
        with open("token.pickle", "rb") as token_file:
            st.session_state.credentials = pickle.load(token_file)
        st.success("🔑 Loaded saved credentials.")
    except Exception as e:
        st.warning(f"Token load error: {e}")
        os.remove("token.pickle")

# Step 1: OAuth
if not st.session_state.credentials:
    st.subheader("1. Authorize Access")
    if st.button("🔐 Authorize Google Calendar"):
        auth_url = get_google_auth_url()
        if auth_url:
            st.markdown(f"👉 [Click here to authorize]({auth_url})")
            st.info("After authorizing, you'll be redirected back here.")

# Step 2: Handle Redirect
query_params = st.query_params
code = query_params.get("code")

if code and not st.session_state.credentials:
    st.write("🔑 Received authorization code. Fetching token...")
    flow = st.session_state.get('oauth_flow')
    if flow:
        try:
            flow.redirect_uri = APP_URL if ENV == "production" else "http://localhost:8501/"
            credentials = flow.fetch_token(code=code)
            st.session_state.credentials = credentials
            with open("token.pickle", "wb") as token_file:
                pickle.dump(credentials, token_file)
            st.success("✅ Google authorization successful!")
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Token fetch error: {e}")
            if 'oauth_flow' in st.session_state:
                del st.session_state['oauth_flow']
            if 'credentials' in st.session_state:
                del st.session_state['credentials']
    else:
        st.error("OAuth session lost. Please re-authorize.")

# Step 3: Fetch and Auto-Summarize Events
if st.session_state.credentials:
    st.subheader("📅 Google Calendar Events")
    try:
        calendar_events_str = get_google_calendar_events(st.session_state.credentials)
        st.text_area("Events:", calendar_events_str, height=200, key="calendar_display")

        if calendar_events_str != "No upcoming events found.":
            with st.spinner("🧠 Summarizing calendar events..."):
                langgraph = create_langgraph_pipeline()
                result = langgraph.invoke({"text": calendar_events_str, "summary": ""})
                st.subheader("📋 Summary of Calendar Events")
                st.write(result.get("summary", "No summary returned."))
        else:
            st.info("No events to summarize.")

    except Exception as e:
        st.error(f"Could not display events. Details: {e}")
        if st.button("Clear Credentials and Re-Authorize"):
            if os.path.exists("token.pickle"):
                os.remove("token.pickle")
            if 'credentials' in st.session_state:
                del st.session_state['credentials']
            if 'oauth_flow' in st.session_state:
                del st.session_state['oauth_flow']
            st.query_params.clear()
            st.rerun()

# Step 4: Manual Summarization
st.subheader("✍️ Or, Enter Any Text to Summarize")
input_text = st.text_area("Enter text:", height=150, key="manual_text")

if st.button("Summarize Manual Text"):
    if input_text:
        with st.spinner("Summarizing input text..."):
            langgraph = create_langgraph_pipeline()
            result = langgraph.invoke({"text": input_text, "summary": ""})
            st.subheader("📝 Summary:")
            st.write(result.get("summary", "No summary returned."))
    else:
        st.warning("Please enter text to summarize.")
