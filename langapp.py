import streamlit as st
import requests
import time
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from langgraph.graph import StateGraph, END
from typing import TypedDict

# Retrieve Hugging Face API token from Streamlit secrets
API_TOKEN = st.secrets["general"]["HUGGINGFACE_API_KEY"]
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

# Define state schema
class SummaryState(TypedDict):
    text: str
    summary: str

# Define summarization function
def summarize_text(state: SummaryState) -> SummaryState:
    text = state["text"]
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    payload = {"inputs": text}

    for _ in range(3):  # Retry logic
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            summary = response.json()[0]["summary_text"]
            return {"text": text, "summary": summary}
        elif response.status_code == 503:
            time.sleep(2)
        else:
            return {"text": text, "summary": f"Error: {response.status_code}, {response.text}"}
    
    return {"text": text, "summary": "Error: Service unavailable after multiple attempts."}

# Build the LangGraph pipeline
def create_langgraph_pipeline():
    builder = StateGraph(SummaryState)
    builder.add_node("summarize", summarize_text)
    builder.set_entry_point("summarize")
    builder.set_finish_point("summarize")  # ✅ Fix here
    return builder.compile()

# --- Google Calendar Authentication and Fetch Events ---
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_credentials():
    """Retrieves credentials for Google Calendar API from session state or triggers OAuth flow."""
    credentials = None
    if "credentials" in st.session_state:
        credentials = st.session_state["credentials"]

    if not credentials:
        # Trigger OAuth flow if no credentials found
        auth_url = get_google_auth_url()
        if st.button("🔐 Authorize Google Calendar to continue."):
            st.write(f"[Click here to authorize Google Calendar]({auth_url})")
        return None
    return credentials

def get_google_auth_url():
    """Generate Google OAuth URL for authentication."""
    flow = InstalledAppFlow.from_client_secrets_file(
        "credentials.json", SCOPES)  # Path to your credentials.json file
    auth_url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true")
    return auth_url

def fetch_google_calendar_events(credentials):
    """Fetch the next 10 events from the user's Google Calendar."""
    service = build('calendar', 'v3', credentials=credentials)
    events_result = service.events().list(
        calendarId='primary', timeMin='2025-01-01T00:00:00Z',
        maxResults=10, singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])
    return events

# --- Streamlit UI ---
st.title("📅 Calendar + 📝 Text Summarizer with LangGraph")

# Get Google Calendar credentials
credentials = get_credentials()

if credentials:
    # If authorized, fetch and display Google Calendar events
    events = fetch_google_calendar_events(credentials)
    if not events:
        st.write("No upcoming events found.")
    else:
        st.write("Upcoming events:")
        for event in events:
            summary = event.get('summary')
            start = event['start'].get('dateTime', event['start'].get('date'))
            st.write(f"{summary} at {start}")
    
    # Input for summarization
    input_text = st.text_area("Enter text to summarize:", height=200)
    
    if st.button("Summarize Text"):
        if input_text:
            with st.spinner("Generating summary..."):
                langgraph = create_langgraph_pipeline()
                result = langgraph.invoke({"text": input_text, "summary": ""})
                summary = result.get("summary", "No summary returned.")
                st.subheader("Summary:")
                st.write(summary)
        else:
            st.warning("Please enter some text to summarize.")
else:
    st.warning("Please authorize Google Calendar to continue.")
