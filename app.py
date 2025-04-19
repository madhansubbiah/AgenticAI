# Import necessary libraries
import os  # Provides functions to interact with the operating system (e.g., file handling)
import json  # Allows parsing and working with JSON data
import pickle  # Used for serializing and deserializing Python objects (e.g., saving credentials)
import requests  # For making HTTP requests, e.g., fetching data from APIs
import streamlit as st  # Streamlit library to create the web application interface
from datetime import datetime, timedelta  # To handle date and time-related operations
from urllib.parse import urlencode  # To encode URL query parameters (used in OAuth flow)
from google_auth_oauthlib.flow import Flow  # For handling OAuth 2.0 authentication with Google
from googleapiclient.discovery import build  # To interact with Google's APIs (e.g., Google Calendar)
from google.auth.transport.requests import Request  # For refreshing expired credentials
from transformers import pipeline  # Hugging Face's pipeline API for NLP tasks like summarization
from typing import TypedDict, List  # For type hinting (specifying types for function arguments and return values)

# Set up environment to allow OAuth to work over an insecure transport (HTTP instead of HTTPS)
#os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Allows OAuth to work with HTTP (instead of HTTPS)

# Load credentials from a JSON file for Google OAuth and other APIs
with open('credentials.json') as f:  # Open the credentials JSON file
    credentials_data = json.load(f)  # Load the credentials data from the file

redirect_uri = credentials_data['web']['redirect_uris'][0]  # Extract redirect URI from the credentials file
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']  # Google Calendar API access scope (read-only)
NEWS_API_KEY = credentials_data.get('NEWS_API_KEY', '')  # News API key for fetching news
WEATHER_API_KEY = credentials_data.get('WEATHER_API_KEY', '')  # Weather API key for fetching weather data

# Initialize the Streamlit app with a title
st.title("🧠 Agentic AI Daily Assistant")  # Set the title of the web app

# Authentication function to initiate Google OAuth
def authenticate_web():
    # Create OAuth flow for Google authentication using credentials file and requested scopes
    flow = Flow.from_client_secrets_file(
        'credentials.json',  # Use the credentials file for OAuth
        scopes=SCOPES,  # Define the scopes (permissions) for accessing Google Calendar
        redirect_uri=redirect_uri  # Set the redirect URI to redirect the user after authentication
    )
    # Generate the authorization URL where the user will log in and authorize access
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    return authorization_url, flow, state  # Return the URL and state for OAuth flow

# Handle OAuth callback after user authorizes access
if 'code' in st.query_params and 'credentials' not in st.session_state:
    received_state = st.query_params.get('state')  # Get the 'state' parameter from the callback URL
    
    # Check if the state matches the one we stored to prevent CSRF attacks
    if os.path.exists('state_temp.json'):
        with open('state_temp.json', 'r') as f:
            stored_state = json.load(f).get('state')
        os.remove('state_temp.json')  # Delete temporary state file after usage
    else:
        stored_state = None

    if stored_state == received_state:  # Proceed only if the state matches
        flow = Flow.from_client_secrets_file(
            'credentials.json',  # Reload the OAuth flow using the credentials file
            scopes=SCOPES,  # Define the requested scopes (Google Calendar access)
            redirect_uri=redirect_uri  # Use the same redirect URI as before
        )
        query_dict = st.query_params  # Extract query parameters from the callback URL
        query_string = urlencode(query_dict, doseq=True)  # URL encode the query parameters
        authorization_response = f"{redirect_uri}?{query_string}"  # Build the full authorization response URL

        try:
            flow.fetch_token(authorization_response=authorization_response)  # Get the access token using the response
            creds = flow.credentials  # Retrieve the credentials object
            st.session_state.credentials = creds  # Store the credentials in the session state

            # Save the credentials for future use (so the user doesn't need to re-authenticate)
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        except Exception as e:
            st.error(f"Authentication failed: {e}")  # Display an error if authentication fails
    else:
        st.error("State mismatch! Possible CSRF attack.")  # Warn about state mismatch (possible CSRF)

# Load saved credentials if they already exist
if 'credentials' not in st.session_state:
    if os.path.exists('token.pickle'):  # Check if there is a saved token file
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)  # Load the credentials from the saved token file

        # If credentials are valid, store them in the session state
        if creds and creds.valid:
            st.session_state.credentials = creds
        # If credentials have expired, refresh them using the refresh token (if available)
        elif creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())  # Refresh the expired credentials
            st.session_state.credentials = creds  # Store the refreshed credentials
            # Save the refreshed credentials for future use
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

# Prompt user to login if credentials are not available
if 'credentials' not in st.session_state:
    authorization_url, flow, state = authenticate_web()  # Start the OAuth process
    # Store the state temporarily to protect against CSRF attacks
    with open('state_temp.json', 'w') as f:
        json.dump({'state': state}, f)

    # Display a button to allow the user to authorize access to Google Calendar
    st.markdown(
        f"""
        <div style="text-align:center;">
            <a href="{authorization_url}" target="_self">
                <button style="padding: 0.75em 1.5em; font-size: 1rem; background-color: #0b8043; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    🔐 Click here to authorize Google Calendar
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.info("Please authorize access to your Google Calendar.")  # Inform the user to authorize
    st.stop()  # Stop execution until user authorizes

# Fetch and display user's calendar events for today and tomorrow
creds = st.session_state.credentials
service = build('calendar', 'v3', credentials=creds)  # Build the Google Calendar API service

now = datetime.utcnow()  # Get the current UTC time
today_start = datetime(now.year, now.month, now.day, tzinfo=datetime.now().astimezone().tzinfo)  # Start of today
tomorrow_end = today_start + timedelta(days=2)  # End of tomorrow

# Fetch events from Google Calendar between today and tomorrow
events_result = service.events().list(
    calendarId='primary',  # Use the primary calendar
    timeMin=today_start.isoformat(),  # Set the start time filter (today)
    timeMax=tomorrow_end.isoformat(),  # Set the end time filter (tomorrow)
    singleEvents=True,  # Ensure recurring events are listed individually
    orderBy='startTime'  # Order the events by start time
).execute()

events = events_result.get('items', [])  # Get the events from the API response

# Display the events on the web app
st.subheader("📅 Today's & Tomorrow's Events")
event_texts = []  # List to store event descriptions for summarization
for event in events:
    try:
        start = event['start'].get('dateTime', event['start'].get('date'))  # Extract start time of the event
        summary = event.get('summary', 'No Title')  # Extract event summary (title)
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))  # Convert start time to datetime object
        if today_start <= start_dt <= tomorrow_end:  # Check if event is within the time range
            st.write(f"• {start_dt.strftime('%Y-%m-%d %H:%M')} — {summary}")  # Display event details
            event_texts.append(f"{start_dt.strftime('%Y-%m-%d %H:%M')} — {summary}")  # Add to event texts for summarization
    except Exception as e:
        st.warning(f"Unexpected error with event: {e}. Event: {event}")  # Display warning if an error occurs with an event
