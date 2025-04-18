import os  # Import the os module for interacting with the operating system
import streamlit as st  # Import Streamlit for creating the web application
from google_auth_oauthlib.flow import Flow  # Import Flow for handling OAuth 2.0 authorization
from googleapiclient.discovery import build  # Import build to create a service object for Google APIs
from transformers import pipeline  # Import pipeline from transformers for using Hugging Face models
from google.auth.transport.requests import Request  # Import Request for refreshing tokens
import pickle  # Import pickle for saving and loading credentials

# Define the scopes for Google Calendar API access
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']  # Request read-only access to the user's calendar

# Function to authenticate with Google Calendar
def authenticate_web():
    flow = Flow.from_client_secrets_file(
        'credentials.json',  # Path to the credentials JSON file
        scopes=SCOPES,  # Scopes defining the level of access
        redirect_uri='https://my-agentic-ai.streamlit.app'  # Redirect URI for the web application
    )
    
    # Generate the authorization URL for the user to log in and grant access
    authorization_url, state = flow.authorization_url(access_type='offline')
    return authorization_url, flow  # Return the authorization URL and the flow object

# Streamlit app title
st.title("Google Calendar Reader with Hugging Face Transformers")

# Step 1: Authenticate with Google
if 'credentials' not in st.session_state:  # Check if credentials are already stored in session state
    if 'code' in st.query_params:  # Check if the authorization code is in the query parameters
        flow = authenticate_web()[1]  # Get the flow object from the authenticate_web function
        # Fetch the access token using the authorization code received from Google
        flow.fetch_token(authorization_response=st.query_params['code'])
        creds = flow.credentials  # Get the credentials (access and refresh tokens)
        st.session_state.credentials = creds  # Store credentials in session state for later use
        
        # Save the credentials to a file
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)  # Save the credentials to a file
        st.success("Authenticated successfully!")  # Display a success message
    else:
        # Check if the token file exists
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)  # Load credentials from the file
            if creds and creds.valid:  # Check if the credentials are valid
                st.session_state.credentials = creds  # Store credentials in session state
            elif creds and creds.expired and creds.refresh_token:  # Refresh the credentials if expired
                creds.refresh(Request())
                st.session_state.credentials = creds  # Store refreshed credentials
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)  # Save the refreshed credentials
            else:
                # If no valid credentials, prompt for authorization
                authorization_url = authenticate_web()[0]  # Get the authorization URL
                st.write(f"[Click here to authorize]({authorization_url})")  # Display the authorization link
        else:
            # If no token file exists, prompt for authorization
            authorization_url = authenticate_web()[0]  # Get the authorization URL
            st.write(f"[Click here to authorize]({authorization_url})")  # Display the authorization link
else:
    creds = st.session_state.credentials  # Retrieve stored credentials from session state
    service = build('calendar', 'v3', credentials=creds)  # Create a service object for the Google Calendar API

    # Step 2: Read events from Google Calendar
    events_result = service.events().list(calendarId='primary', maxResults=10, singleEvents=True,
                                          orderBy='startTime').execute()  # Fetch upcoming events from the user's calendar
    events = events_result.get('items', [])  # Get the list of events from the response

    if not events:  # Check if there are no upcoming events
        st.write('No upcoming events found.')  # Display a message if no events are found
    else:
        st.write("Upcoming events:")  # Display a header for the events list
        for event in events:  # Iterate through the list of events
            start = event['start'].get('dateTime', event['start'].get('date'))  # Get the start time of the event
            st.write(f"{start}: {event['summary']}")  # Display the event start time and summary

        # Step 3: Process events with Hugging Face Transformers
        st.write("Processing events with Hugging Face Transformers...")  # Display a message indicating processing
        
        # Load a Hugging Face model for summarization
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")  # You can choose a different model if desired

        # Prepare the input for the model
        event_summaries = "\n".join([f"{start}: {event['summary']}" for event in events])  # Create a summary of events
        prompt = f"Here are my upcoming events:\n{event_summaries}\nCan you summarize these events for me?"  # Create a prompt for the model

        # Get the response from the model
        response = summarizer(prompt, max_length=50, min_length=25, do_sample=False)  # Run the summarization
        st.write("Model Response:")  # Display a header for the model response
        st.write(response[0]['summary_text'])  # Display the summary text from the model
