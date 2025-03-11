import os
import time
import streamlit as st
from dotenv import load_dotenv
from apps.jsondb import list_agents, list_threads, update_agent

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

if "agent" not in st.session_state:
    st.session_state.agent = {
        "id": None,
        "name": None,
        "model": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        "description": None,
        "instructions": "You are a helpful agent.",
        "tools": {},
        "top_p": 1.0,
        "temperature": 0.7,
        "response_format": "auto",
    }

@st.dialog("Agent Details")
def agent_modal(state: str):
    st.session_state.agent["name"] = st.text_input(":blue[**Agent Name:**]", st.session_state.agent["name"])
    st.session_state.agent["instructions"] = st.text_area(":blue[**System Message:**]", st.session_state.agent["instructions"], key="agent_prompt_modal")

    if state == "new":
        if st.button("Save New Agent"):
            st.session_state.agent["id"] = None
            st.session_state.thread_id = None
            st.session_state.messages = []
            st.info(f"Start chatting to save the new agent.", icon="ℹ️")
            time.sleep(2)
            st.rerun()
    else:
        if st.button("Update Agent"):
            update_agent()
            st.info(f"Agent updated!", icon="ℹ️")
            time.sleep(1)
            st.rerun()

with st.sidebar:
    agents = list_agents()
    # create a list of agents names
    agent_names = [agent["name"] for agent in agents]
    # select the agent else None
    agent_index = agent_names.index(st.session_state.agent["name"]) if st.session_state.agent["name"] in agent_names else None
    agent_selected = st.selectbox(":blue[**Select an Agent:**]", agent_names, index=agent_index)

    # select an agent
    if agent_selected:
        st.session_state.agent["name"] = agent_selected
        st.session_state.agent["id"] = agents[agent_names.index(agent_selected)]["id"]
        st.session_state.agent["instructions"] = agents[agent_names.index(agent_selected)]["prompt"]

    # update an agent
    if st.button(":green[**⚙️Update Agent**]"):
        agent_modal("update")

    # create a new agent
    if st.button(":green[**➕New Agent**]"):
        agent_modal("new")

    # populate the agent system message
    st.session_state.agent["instructions"] = st.text_area(":blue[**System Message:**]", st.session_state.agent["instructions"])

    # update the system message
    if st.button(":green[**⚙️Update System Message**]"):
        st.toast("System message updated!", icon="✅")
        update_agent()

    threads = list_threads(st.session_state.agent["id"])
    # create a list of threads
    thread_ids = [thread["id"] for thread in threads]
    # select the thread else None
    thread_index = thread_ids.index(st.session_state.thread_id) if st.session_state.thread_id in thread_ids else None
    thread_selected = st.selectbox(":blue[**Select a Thread:**]", thread_ids, index=thread_index)

    if thread_selected and st.session_state.thread_id != thread_selected:
        st.session_state.thread_id = thread_selected
        # populate the messages
        for thread in threads:
            if thread["id"] == thread_selected:
                st.session_state.messages = thread["messages"]

    if st.button(":green[**➕New Thread**]"):
        st.session_state.thread_id = None
        st.session_state.messages = []

pages = {
    "Resources": [
        st.Page("apps/agents_create_use.py", title="Chat with Agent", icon="💬"),
        st.Page("apps/agents_task.py", title="Health Care Planner", icon="👩‍⚕️"),
        st.Page("apps/agents_functions.py", title="Multi-Function Agent", icon="🔀"),
    ],
    "Manage": [
        st.Page("apps/list_agents.py", title="List Agents", icon="⚙️"),
        st.Page("apps/delete_agents.py", title="Delete Agents", icon="⚙️"),
    ],
}

pg = st.navigation(pages)
pg.run()
