import os
import streamlit as st
import requests
import time
from langgraph.graph import StateGraph
from typing import TypedDict
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import pickle

# Constants
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
API_TOKEN = st.secrets["general"]["HUGGINGFACE_API_KEY"]
STREAMLIT_APP_URL = st.secrets["general"]["STREAMLIT_APP_URL"]

# Define state schema
class SummaryState(TypedDict):
    text: str
    summary: str

# Summarization function
def summarize_text(state: SummaryState) -> SummaryState:
    text = state["text"]
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    payload = {"inputs": text}

    for attempt in range(3):  # Retry logic
        st.write(f"⏳ Attempt {attempt + 1} to summarize text")
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            summary = response.json()[0]["summary_text"]
            return {"text": text, "summary": summary}
        elif response.status_code == 503:
            time.sleep(2)
        else:
            st.write(f"❌ Error: {response.status_code}, {response.text}")
            return {"text": text, "summary": f"Error: {response.status_code}, {response.text}"}

    return {"text": text, "summary": "Error: Service unavailable after multiple attempts."}

# Build LangGraph
def create_langgraph_pipeline():
    builder = StateGraph(SummaryState)
    builder.add_node("summarize", summarize_text)
    builder.set_entry_point("summarize")
    builder.set_finish_point("summarize")
    return builder.compile()

# Google Auth URL creation
def get_google_auth_url():
    redirect_uri = STREAMLIT_APP_URL if os.getenv("STREAMLIT_ENV") == "production" else "http://localhost:8501/"
    st.write(f"🔄 Redirect URI: {redirect_uri}")
    
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    flow.redirect_uri = redirect_uri
    auth_url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true")
    return auth_url, flow

# Build Google Calendar service
def get_calendar_service(creds):
    return build("calendar", "v3", credentials=creds)

# Fetch events
def get_google_calendar_events(creds):
    service = get_calendar_service(creds)
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
        events_str += f"- {event['summary']} at {start_time}\n"
    
    return events_str

# UI
st.title("📅 Calendar + 📝 Text Summarizer with LangGraph")

# Auth button
auth_clicked = st.button("🔐 Authorize Google Calendar to continue.")
query_params = st.query_params
st.write("🌐 Query Params:", query_params)

if auth_clicked:
    st.write("🔧 Generating Google OAuth URL...")
    auth_url, flow = get_google_auth_url()
    st.write("🔗 [Click here to authorize](%s)" % auth_url)

    code = query_params.get("code", [None])[0]
    st.write("📩 OAuth Code:", code)

    if code:
        try:
            flow.fetch_token(code=code)
            creds = flow.credentials
            st.success("✅ Authorization successful!")

            with open("token.pickle", "wb") as token:
                pickle.dump(creds, token)
            
            # Fetch events
            st.write("📅 Fetching calendar events...")
            events = get_google_calendar_events(creds)
            st.subheader("🗓️ Google Calendar Events")
            st.write(events)

        except Exception as e:
            st.error(f"❌ Error during authorization: {e}")
            st.write(e)

# Text summarizer
input_text = st.text_area("✍️ Enter text to summarize:", height=200)

if st.button("📃 Summarize Text"):
    if input_text:
        with st.spinner("Generating summary..."):
            langgraph = create_langgraph_pipeline()
            result = langgraph.invoke({"text": input_text, "summary": ""})
            summary = result.get("summary", "No summary returned.")
            st.subheader("✅ Summary")
            st.write(summary)
    else:
        st.warning("⚠️ Please enter some text to summarize.")
