import json
import datetime
import streamlit as st
from typing import List, Dict, Any

# list all agents from db_agents.json
def list_agents():
    with open("data/db_agents.json", "r") as f:
        return json.load(f)

# save all agents to db_agents.json
def save_agents(agents: List[Dict[str, Any]]):
    with open("data/db_agents.json", "w") as f:
        json.dump(agents, f, indent=4)

# save agent to db_agents.json
def save_agent():
    agents = list_agents()
    agents.append({
        "id": st.session_state.agent["id"],
        "timestamp": datetime.datetime.now().isoformat(),
        "name": st.session_state.agent["name"],
        "model": st.session_state.agent["model"],
        "prompt": st.session_state.agent["instructions"],
        "tools": []
    })

    save_agents(agents)

# update agent prompt to db_agents.json
def update_agent():
    agents = list_agents()
    for agent in agents:
        if agent["id"] == st.session_state.agent["id"]:
            agent["name"] = st.session_state.agent["name"]
            agent["prompt"] = st.session_state.agent["instructions"]

    save_agents(agents)

# delete agent from db_agents.json
def delete_agent(agent_id: str):
    agents = list_agents()
    for agent in agents:
        if agent["id"] == agent_id:
            agents.remove(agent)

    save_agents(agents)

# get all threads from db_threads.json
def get_threads():
    with open("data/db_threads.json", "r") as f:
        return json.load(f)

# save all threads to db_threads.json
def save_threads(threads: List[Dict[str, Any]]):
    with open("data/db_threads.json", "w") as f:
        json.dump(threads, f, indent=4)

# list all threads relevant to an agent from db_threads.json
def list_threads(agent_id: str):
    threads = get_threads()
    return [thread for thread in threads if thread["agent_id"] == agent_id]

# save thread to db_threads.json
def save_thread():
    threads = get_threads()
    threads.append({
        "id": st.session_state.thread_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "agent_id": st.session_state.agent["id"],
        "messages": []
    })

    save_threads(threads)

# update thread with messages to db_threads.json
def update_thread(role: str, content: List[Dict[str, Any]]):
    threads = get_threads()
    for thread in threads:
        if thread["id"] == st.session_state.thread_id:
            thread["messages"].append({
                "timestamp": datetime.datetime.now().isoformat(),
                "role": role,
                "content": content
            })

    save_threads(threads)

# delete a thread from db_threads.json
def delete_thread(thread_id: str):
    threads = get_threads()
    for thread in threads:
        if thread["id"] == thread_id:
            threads.remove(thread)

    save_threads(threads)
