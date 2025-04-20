import os
import streamlit as st
import requests
import time
from langgraph.graph import StateGraph, END
from typing import TypedDict
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pickle
import json

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

# Google Calendar OAuth2 Setup
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_google_auth_url():
    """Generate Google OAuth URL for authentication."""
    # Detect the redirect URI dynamically from the current environment
    if os.getenv("STREAMLIT_ENV") == "production":
        # Dynamically fetch Streamlit URL in production using st.secrets
        redirect_uri = st.secrets["general"]["STREAMLIT_APP_URL"]
    else:
        # Default to localhost for local development
        redirect_uri = 'http://localhost:8501/'

    # Initialize the flow and set the redirect URI dynamically
    flow = InstalledAppFlow.from_client_secrets_file(
        "credentials.json", SCOPES)
    flow.redirect_uri = redirect_uri  # Use the dynamically set URI
    auth_url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true")
    return auth_url

def get_calendar_service(credentials):
    """Build and return the Google Calendar service."""
    return build("calendar", "v3", credentials=credentials)

def get_google_calendar_events(credentials):
    """Fetch Google Calendar events."""
    service = get_calendar_service(credentials)
    events_result = service.events().list(calendarId='primary', timeMin='2025-01-01T00:00:00Z', maxResults=10, singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])
    
    if not events:
        return "No upcoming events found."
    
    events_str = "Upcoming events:\n"
    for event in events:
        start_time = event['start'].get('dateTime', event['start'].get('date'))
        events_str += f"{event['summary']} at {start_time}\n"
    
    return events_str

# Streamlit UI
st.title("📅 Google Calendar + 📝 Text Summarizer with LangGraph")

# Button to trigger Google Calendar Authorization
if st.button("🔐 Authorize Google Calendar to continue."):
    auth_url = get_google_auth_url()
    st.write(f"Please [authorize access](%s)" % auth_url)

    # The code will need to handle the OAuth flow and store the credentials
    code = st.experimental_get_query_params().get("code", [None])[0]
    
    if code:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json", SCOPES)
        flow.redirect_uri = st.secrets["general"]["STREAMLIT_APP_URL"]  # Redirect URI used for production
        credentials = flow.fetch_token(code=code)
        with open("token.pickle", "wb") as token:
            pickle.dump(credentials, token)
        st.success("Authorization successful. Now you can fetch events.")

        # Fetch and display calendar events
        events = get_google_calendar_events(credentials)
        st.subheader("Google Calendar Events:")
        st.write(events)
    
# Text summarization section
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
