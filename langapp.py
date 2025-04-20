import streamlit as st
import requests
import time
from google_auth_oauthlib.flow import Flow
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

# === Google OAuth Setup ===
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CLIENT_SECRETS_FILE = "credentials.json"

def get_google_calendar_service():
    if "credentials" not in st.session_state:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES,
            redirect_uri=st.experimental_get_url()
        )
        auth_url, _ = flow.authorization_url(prompt='consent')
        st.session_state.flow = flow
        # Make the URL clickable with Markdown
        st.markdown(f"[Click here to authorize Google Calendar access]({auth_url})", unsafe_allow_html=True)
        st.stop()
    creds = st.session_state["credentials"]
    return build("calendar", "v3", credentials=creds)

def fetch_calendar_events(service):
    events_result = service.events().list(calendarId="primary", timeMin="2025-01-01T00:00:00Z",
                                          maxResults=10, singleEvents=True, orderBy="startTime").execute()
    events = events_result.get("items", [])

    if not events:
        return "No upcoming events found."

    event_text = ""
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        event_text += f"{start}: {event['summary']}\n"
    return event_text

# Streamlit UI
st.title("📅 Calendar + 📝 Text Summarizer with LangGraph")

# --- Section: Google Calendar Events Summary ---
st.subheader("1️⃣ Summarize Google Calendar Events")

query_params = st.query_params  # ✅ updated from experimental_get_query_params
if "code" in query_params and "flow" in st.session_state:
    flow = st.session_state.flow
    flow.fetch_token(authorization_response=st.experimental_get_url())
    creds = flow.credentials
    st.session_state["credentials"] = creds
    st.success("✅ Authorized with Google Calendar!")

if "credentials" in st.session_state:
    try:
        service = get_google_calendar_service()
        with st.spinner("Fetching events..."):
            calendar_text = fetch_calendar_events(service)
            st.code(calendar_text)

        if st.button("Summarize Calendar Events"):
            with st.spinner("Summarizing..."):
                langgraph = create_langgraph_pipeline()
                result = langgraph.invoke({"text": calendar_text, "summary": ""})
                st.subheader("📝 Calendar Summary:")
                st.write(result.get("summary", "No summary returned."))
    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("🔐 Authorize Google Calendar to continue.")

# --- Section: Text Summarization ---
st.subheader("2️⃣ Text Summarizer")

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
