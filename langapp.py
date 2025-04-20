import streamlit as st
import requests
import time
from langgraph import LangGraph, Node

# Retrieve the Hugging Face API token from Streamlit secrets
API_TOKEN = st.secrets["general"]["HUGGINGFACE_API_KEY"]
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

# Function to call the Hugging Face Inference API
def summarize_text(text):
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    payload = {"inputs": text}
    
    for _ in range(3):  # Retry up to 3 times
        response = requests.post(API_URL, headers=headers, json=payload)
        
        if response.status_code == 200:
            return response.json()[0]['summary_text']
        elif response.status_code == 503:
            time.sleep(2)  # Wait for 2 seconds before retrying
        else:
            return f"Error: {response.status_code}, {response.text}"
    
    return "Error: Service is currently unavailable after multiple attempts."

# Create a LangGraph pipeline
def create_langgraph_pipeline():
    # Define a node for summarization
    summarize_node = Node(
        func=summarize_text,
        input_key="text",
        output_key="summary"
    )

    # Create a LangGraph
    graph = LangGraph(nodes={"summarize": summarize_node})

    return graph

# --- Streamlit UI ---
st.title("📝 Text Summarization with Hugging Face API and LangGraph")

input_text = st.text_area("Enter text to summarize:", height=200)

if st.button("Summarize Text"):
    if input_text:
        with st.spinner("Generating summary..."):
            # Create the LangGraph pipeline
            langgraph = create_langgraph_pipeline()
            # Run the LangGraph with the input text
            result = langgraph.run({"text": input_text})
            summary = result["summary"]
            st.subheader("Summary:")
            st.write(summary)  # Display the summary
    else:
        st.warning("Please enter some text to summarize.")
