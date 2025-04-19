import os
import json
import pickle
import streamlit as st
from urllib.parse import urlencode
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from transformers import pipeline
from datetime import datetime, timedelta

# Allow insecure transport for local testing (ignored on Streamlit Cloud)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Load credentials
with open('credentials.json') as f:
    credentials_data = json.load(f)

redirect_uri = credentials_data['web']['redirect_uris'][0]
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

st.set_page_config(page_title="Google Calendar Reader")
st.title("🗓 Google Calendar Reader with Transformers")
st.write(f"🔁 Redirect URI: `{redirect_uri}`")

# --- Helper: OAuth flow ---
def authenticate_web():
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return authorization_url, flow, state

# --- 1. Handle redirect with ?code= ---
if 'code' in st.query_params and 'credentials' not in st.session_state:
    received_state = st.query_params.get('state')
    stored_state = None

    if os.path.exists('state_temp.json'):
        with open('state_temp.json', 'r') as f:
            stored_state = json.load(f).get('state')
        os.remove('state_temp.json_
