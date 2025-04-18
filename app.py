import os
import json
import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from transformers import pipeline
from google.auth.transport.requests import Request
import pickle

# Allow insecure transport (development only)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Load OAuth credentials
with open('credentials.json') as f:
    credentials_data = json.load(f)

redirect_uri = credentials_data['web']['redirect_uris'][0]
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def authenticate_web():
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    authorization_url, state = flow.authorization_url(access_type='offline')
    return authorization_url, flow, state

st.title("Google Calendar Reader with Hugging Face Transformers")
st.write(f"Redirect URI: {redirect_uri}")

# Step 1: Authenticate
if 'credentials' not in st.session_state:
    if 'code' in st.query_params:
        code = st.query_params['code']
        received_state = st.query_params.get('state')
        st.write(f"Query Params: {st.query_params}")
        st.write(f"Received State: {received_state}")

        # Load the stored state from file
        if os.path.exists('state_temp.json'):
            with open('state_temp.json', 'r') as f:
                stored_state = json.load(f).get('state')
            os.remove('state_temp.json')
        else:
            stored_state = None

        st.write(f"Stored State: {stored_state}")

        if stored_state and stored_state == received_state:
            # Recreate the flow with same redirect URI and scopes
            flow = Flow.from_client_secrets_file(
                'credentials.json',
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )
            # Rebuild the flow state (required for validation)
            flow.fetch_token(authorization_response=st.experimental_get_query_params())

            creds = flow.credentials
            st.session_state.credentials = creds
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
            st.success("Authenticated successfully!")
        else:
            st.error("State mismatch! Possible CSRF attack.")
    else:
        # Try loading token from previous session
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
            else:
                authorization_url, flow, state = authenticate_web()
                # Save state to file
                with open('state_temp.json', 'w') as f:
                    json.dump({'state': state}, f)
                st.write(f"[Click here to authorize]({authorization_url})")
        else:
            authorization_url, flow, state = authenticate_web()
            # Save state to file
            with open('state_temp.json', 'w') as f:
                json.dump({'state': state}, f)
            st.write(f"[Click here to authorize]({authorization_url})")

# Step 2: Display events and summarize
else:
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
        st.write('No upcoming events found.')
    else:
        st.write("Upcoming events:")
        event_texts = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'No Title')
            st.write(f"{start}: {summary}")
            event_texts.append(f"{start}: {summary}")

        # Step 3: Use Hugging Face summarization
        st.write("Processing events with Hugging Face Transformers...")
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        prompt = f"Here are my upcoming events:\n" + "\n".join(event_texts) + "\nCan you summarize these?"
        response = summarizer(prompt, max_length=50, min_length=25, do_sample=False)
        st.write("Model Response:")
        st.write(response[0]['summary_text'])
