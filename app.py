import os
import json
import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from transformers import pipeline
from google.auth.transport.requests import Request
import pickle

# Load credentials from the JSON file
with open('credentials.json') as f:
    credentials_data = json.load(f)

# Extract the redirect URI
redirect_uri = credentials_data['web']['redirect_uris'][0]  # Ensure this is HTTPS

# Define the scopes for Google Calendar API access
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Function to authenticate with Google Calendar
def authenticate_web():
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    
    authorization_url, state = flow.authorization_url(access_type='offline')
    return authorization_url, flow

# Streamlit app title
st.title("Google Calendar Reader with Hugging Face Transformers")

# Print the redirect URI
st.write(f"Redirect URI: {redirect_uri}")

# Step 1: Authenticate with Google
if 'credentials' not in st.session_state:
    if 'code' in st.query_params:
        flow = authenticate_web()[1]
        st.write(f"Query Params: {st.query_params}")
        #flow.fetch_token(authorization_response=st.query_params['code'])
        flow.fetch_token(authorization_response=redirect_uri)
        creds = flow.credentials
        st.session_state.credentials = creds
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
        st.success("Authenticated successfully!")
    else:
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
                authorization_url = authenticate_web()[0]
                st.write(f"[Click here to authorize]({authorization_url})")
        else:
            authorization_url = authenticate_web()[0]
            st.write(f"[Click here to authorize]({authorization_url})")
else:
    creds = st.session_state.credentials
    service = build('calendar', 'v3', credentials=creds)

    # Step 2: Read events from Google Calendar
    events_result = service.events().list(calendarId='primary', maxResults=10, singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])

    if not events:
        st.write('No upcoming events found.')
    else:
        st.write("Upcoming events:")
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            st.write(f"{start}: {event['summary']}")

        # Step 3: Process events with Hugging Face Transformers
        st.write("Processing events with Hugging Face Transformers...")
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        event_summaries = "\n".join([f"{start}: {event['summary']}" for event in events])
        prompt = f"Here are my upcoming events:\n{event_summaries}\nCan you summarize these events for me?"
        response = summarizer(prompt, max_length=50, min_length=25, do_sample=False)
        st.write("Model Response:")
        st.write(response[0]['summary_text'])
