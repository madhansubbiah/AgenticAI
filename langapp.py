import streamlit as st
import requests
import json
from langgraph.graph import StateGraph
from typing import TypedDict

# --- Load API key from Streamlit secrets ---
HUGGINGFACE_API_KEY = st.secrets["general"]["HUGGINGFACE_API_KEY"]

# Print the API key (for debugging purposes only)
st.write("Hugging Face API Key:", HUGGINGFACE_API_KEY)

# Update the API URL for the sentence-transformers model
HF_API_URL = "https://api-inference.huggingface.co/models/sentence-transformers/all-mpnet-base-v2"
headers = {
    "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
    "Content-Type": "application/json"
}

# --- State Schema ---
class State(TypedDict):
    input_text: str
    embeddings: list

# --- LangGraph Node ---
def embed_node(state: State) -> State:
    text = state["input_text"]

    payload = {
        "inputs": text
    }

    response = requests.post(HF_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    embeddings = response.json()  # This will contain the embeddings

    return {
        "input_text": text,
        "embeddings": embeddings
    }

# --- Build Graph ---
builder = StateGraph(State)
builder.add_node("embed", embed_node)
builder.set_entry_point("embed")
builder.set_finish_point("embed")
graph = builder.compile()

# --- Streamlit UI ---
st.title("🧠 LangGraph + Hugging Face Sentence Embeddings")

input_text = st.text_area("Enter text to get embeddings:", height=200)

if st.button("Get Embeddings"):
    if input_text:
        with st.spinner("Generating embeddings..."):
            result = graph.invoke({"input_text": input_text})
            st.subheader("Embeddings:")
            st.write(result["embeddings"])
    else:
        st.warning("Please enter some text to get embeddings.")