import os
import json
import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from transformers import pipeline
from google.auth.transport.requests import Request
import pickle

# Allow insecure transport for testing purposes (not recommended for production)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

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
    return authorization_url, flow, state  # Return the authorization URL, flow object, and state

# Streamlit app title
st.title("Google Calendar Reader with Hugging Face Transformers")

# Print the redirect URI
st.write(f"Redirect URI: {redirect_uri}")

# Step 1: Authenticate with Google
if 'credentials' not in st.session_state:
    if 'code' in st.query_params:
        flow = authenticate_web()[1]
        st.write(f"Query Params: {st.query_params}")

        # Log the received state
        received_state = st.query_params.get('state')
        st.write(f"Received State: {received_state}")

        # Log the stored state for comparison
        stored_state = st.session_state.get('state')
        st.write(f"Stored State: {stored_state}")

        # Fetch the token using the authorization code from the query parameters
        try:
            # Ensure the state is stored in session state for validation
            if stored_state and stored_state == received_state:
                flow.fetch_token(authorization_response=st.query_params['code'])
                creds = flow.credentials
                st.session_state.credentials = creds
                
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
                st.success("Authenticated successfully!")
            else:
                st.error("State mismatch! Possible CSRF attack.")
        except Exception as e:
            st.error(f"Error during authentication: {e}")
    else:
        # Clear previous state if it exists
        if 'state' in st.session_state:
            del st.session_state['state']

        # Check if the token file exists
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
                # Generate the authorization URL and store the state
                authorization_url, flow, state = authenticate_web()
                st.session_state.state = state  # Store the state in session state
                st.write(f"[Click here to authorize]({authorization_url})")
        else:
            # Generate the authorization URL and store the state
            authorization_url, flow, state = authenticate_web()
            st.session_state.state = state  # Store the state in session state
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
