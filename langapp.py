import streamlit as st
import requests
import time
from langgraph.graph import StateGraph, END
from typing import TypedDict

# Retrieve the Hugging Face API token from Streamlit secrets
API_TOKEN = st.secrets["general"]["HUGGINGFACE_API_KEY"]
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

# Define the state schema
class SummaryState(TypedDict):
    text: str
    summary: str

# Function to call the Hugging Face Inference API
def summarize_text(state: SummaryState) -> SummaryState:
    text = state["text"]
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    payload = {"inputs": text}
    
    for _ in range(3):  # Retry up to 3 times
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            summary = response.json()[0]['summary_text']
            return {"text": text, "summary": summary}
        elif response.status_code == 503:
            time.sleep(2)
        else:
            return {"text": text, "summary": f"Error: {response.status_code}, {response.text}"}
    
    return {"text": text, "summary": "Error: Service is currently unavailable after multiple attempts."}

# Create a LangGraph pipeline
def create_langgraph_pipeline():
    builder = StateGraph(SummaryState)
    builder.add_node("summarize", summarize_text)
    builder.set_entry_point("summarize")
    builder.set_finish_point(END)
    builder.add_edge("summarize", END)
    return builder.compile()

# --- Streamlit UI ---
st.title("📝 Text Summarization with Hugging Face API and LangGraph")

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
