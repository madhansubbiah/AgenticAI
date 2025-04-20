import streamlit as st
from transformers import pipeline
import os

# Set up proxy
# proxy = "http://webproxy.merck.com:8080"
# os.environ['HTTP_PROXY'] = proxy
# os.environ['HTTPS_PROXY'] = proxy

# --- Initialize Summarization Pipeline ---
summarizer_pipeline = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

# --- Streamlit UI ---
st.title("📝 Text Summarization with DistilBART")

input_text = st.text_area("Enter text to summarize:", height=200)

if st.button("Summarize Text"):
    if input_text:
        with st.spinner("Generating summary..."):
            summary = summarizer_pipeline(input_text, max_length=130, min_length=30, do_sample=False)
            st.subheader("Summary:")
            st.write(summary[0]['summary_text'])  # Display the summary
    else:
        st.warning("Please enter some text to summarize.")
