import os
import json
import pickle
import streamlit as st
from urllib.parse import urlencode
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from transformers import pipeline

# Allow local test only; Streamlit Cloud is secure by default
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Load credentials
with open('credentials.json') as f:
    credentials_data = json.load(f)

redirect_uri = credentials_data['web']['redirect_uris'][0]
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

st.set_page_config(page_title="Google Calendar Reader", layout="centered")
st.title("📅 Google Calendar Reader with Transformers")

# ---- Helper
def authenticate_web():
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return auth_url, flow, state

# ---- OAuth callback
query_params = st.query_params
if "code" in query_params and "credentials" not in st.session_state:
    code = query_params.get("code")
    state = query_params.get("state")

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
        full_url = f"{redirect_uri}?code={code}&state={state}"

        try:
            flow.fetch_token(authorization_response=full_url)
            creds = flow.credentials
            st.session_state.credentials = creds

            with open("token.pickle", "wb") as f:
                pickle.dump(creds, f)

            # Clear query params via JS
            st.markdown("""
            <script>
                window.history.replaceState({}, document.title, window.location.pathname);
                window.location.reload();
            </script>
            """, unsafe_allow_html=True)

            st.stop()
        except Exception as e:
            st.error(f"OAuth error: {e}")
    else:
        st.error("Invalid state. Try again.")
        st.stop()

# ---- Load from pickle
if "credentials" not in st.session_state:
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)
        if creds and creds.valid:
            st.session_state.credentials = creds
        elif creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            st.session_state.credentials = creds
            with open("token.pickle", "wb") as f:
                pickle.dump(creds, f)

# ---- Show auth if still not done
if "credentials" not in st.session_state:
    auth_url, flow, state = authenticate_web()
    with open("state_temp.json", "w") as f:
        json.dump({"state": state}, f)

    st.markdown(
        f"""
        <div style="text-align:center;">
            <a href="{auth_url}">
                <button style="padding: 0.75em 1.5em; font-size: 1rem; background-color: #0b8043; color: white; border: none; border-radius: 5px;">
                    🔐 Click here to authorize Google Calendar
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.info("Please authorize Google Calendar access.")
    st.stop()

# ---- Authenticated: fetch calendar events
creds = st.session_state.credentials
service = build("calendar", "v3", credentials=creds)

events_result = service.events().list(
    calendarId="primary",
    maxResults=10,
    singleEvents=True,
    orderBy="startTime"
).execute()

events = events_result.get("items", [])

if not events:
    st.write("📭 No upcoming events.")
else:
    st.subheader("🗓 Upcoming Events")
    event_texts = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        title = event.get("summary", "No Title")
        st.markdown(f"- **{start}** — {title}")
        event_texts.append(f"{start}: {title}")

    # Summarize with Hugging Face
    st.write("🔍 Summarizing using Transformers...")
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    prompt = "Summarize the following events:\n" + "\n".join(event_texts)
    result = summarizer(prompt, max_length=60, min_length=25, do_sample=False)
    st.success("📋 Summary:")
    st.write(result[0]['summary_text'])
