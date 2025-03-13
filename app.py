import os
import datetime
import streamlit as st
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

st.set_page_config(page_title="AI Agent", page_icon="✨", layout="wide")

st.logo(
    "https://azure.microsoft.com/svghandler/cognitive-services-openai-service/?width=600&height=500",
    link="https://ai.azure.com",
    icon_image="https://api.nuget.org/v3-flatcontainer/aspire.azure.ai.openai/9.0.0-preview.5.24551.3/icon",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 3rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize session state
if "project_connection" not in st.session_state:
    st.session_state.project_connection = os.getenv("AIPROJECT_CONNECTION_STRING")

if "deployment_name" not in st.session_state:
    st.session_state.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

if "endpoint" not in st.session_state:
    st.session_state.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

if "api_key" not in st.session_state:
    st.session_state.api_key = os.getenv("AZURE_OPENAI_API_KEY")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

if "client" not in st.session_state:
    st.session_state.client = None

if "agent" not in st.session_state:
    st.session_state.agent = {
        "id": None,
        "name": f"agent-{datetime.datetime.now().isoformat()}",
        "model": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        "description": None,
        "instructions": (
            "You are a helpful triaging agent. You can use your tools to delegate questions to other appropriate agents."
            "Use the response from other agents to answer the question. Do not rely on your own knowledge."
            "Other than greetings, do not answer any questions yourself."
            ),
        "tools": {},
        "top_p": 1.0,
        "temperature": 0.7,
        "response_format": "auto",
    }

with st.sidebar:
    st.session_state.agent["instructions"] = st.text_area(":blue[**Triage Agent:**]", st.session_state.agent["instructions"])
    st.session_state.agent["temperature"] = st.slider(":blue[**Temperature:**]", 0.0, 2.0, st.session_state.agent["temperature"], 0.1)
    st.session_state.agent["top_p"] = st.slider(":blue[**Top P:**]", 0.0, 2.0, st.session_state.agent["top_p"], 0.1)

pages = {
    "AI Agent": [
        st.Page("apps/agents_sdk.py", title="Agents SDK", icon="🤖"),
    ],
}

pg = st.navigation(pages)
pg.run()
