import os
import streamlit as st
import requests
import time
from langgraph.graph import StateGraph, END
from typing import TypedDict
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pickle


# Load secrets
API_TOKEN = st.secrets["general"]["HUGGINGFACE_API_KEY"]
APP_URL = st.secrets["general"]["STREAMLIT_APP_URL"]
ENV = st.secrets["general"].get("STREAMLIT_ENV", "development")  # default to development
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Debug: Show environment and secrets
st.write("🔧 Environment:", ENV)
st.write("🔧 App URL:", APP_URL)

# Define state schema
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
            time.sleep(2)
        else:
            return {"text": text, "summary": f"Error: {response.status_code}, {response.text}"}
    
    return {"text": text, "summary": "Error: Service unavailable after multiple attempts."}

# LangGraph setup
def create_langgraph_pipeline():
    builder = StateGraph(SummaryState)
    builder.add_node("summarize", summarize_text)
    builder.set_entry_point("summarize")
    builder.set_finish_point("summarize")
    return builder.compile()

# Google Calendar
def get_google_auth_url():
    redirect_uri = APP_URL if ENV == "production" else "http://localhost:8501/"
    st.write("🔗 Using redirect URI:", redirect_uri)

    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    flow.redirect_uri = redirect_uri
    auth_url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true")
    return auth_url, flow

def get_calendar_service(credentials):
    return build("calendar", "v3", credentials=credentials)

def get_google_calendar_events(credentials):
    service = get_calendar_service(credentials)
    events_result = service.events().list(
        calendarId='primary',
        timeMin='2025-01-01T00:00:00Z',
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    if not events:
        return "No upcoming events found."
    
    events_str = "Upcoming events:\n"
    for event in events:
        start_time = event['start'].get('dateTime', event['start'].get('date'))
        events_str += f"{event['summary']} at {start_time}\n"
    return events_str

# ---------------- Streamlit UI ---------------- #

st.title("📅 Calendar + 📝 Text Summarizer with LangGraph")

# Step 1: Google Auth
if st.button("🔐 Authorize Google Calendar to continue."):
    auth_url, flow = get_google_auth_url()
    st.markdown(f"👉 [Click here to authorize]({auth_url})")

# Step 2: Handle redirect
query_params = st.query_params
code = query_params.get("code", None)
if code:
    st.write("🔑 Received authorization code:", code)
    redirect_uri = APP_URL if ENV == "production" else "http://localhost:8501/"
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    flow.redirect_uri = redirect_uri
    credentials = flow.fetch_token(code=code)
    st.success("✅ Google authorization successful!")

    # Save token for debugging (or future use)
    with open("token.pickle", "wb") as token_file:
        pickle.dump(credentials, token_file)

    # Show calendar events
    st.subheader("📅 Google Calendar Events")
    try:
        events = get_google_calendar_events(credentials)
        st.text(events)

        # Offer to summarize calendar events
        if st.button("📝 Summarize Calendar Events"):
            langgraph = create_langgraph_pipeline()
            result = langgraph.invoke({"text": events, "summary": ""})
            st.subheader("📋 Summary of Calendar Events")
            st.write(result.get("summary", "No summary returned."))

    except Exception as e:
        st.error(f"Failed to fetch calendar events: {e}")

# Step 3: Manual text summarization
st.subheader("✍️ Enter Text to Summarize")
input_text = st.text_area("Enter your text here:", height=200)

if st.button("Summarize Text"):
    if input_text:
        with st.spinner("Summarizing..."):
            langgraph = create_langgraph_pipeline()
            result = langgraph.invoke({"text": input_text, "summary": ""})
            summary = result.get("summary", "No summary returned.")
            st.subheader("📝 Summary:")
            st.write(summary)
    else:
        st.warning("Please enter text to summarize.")
