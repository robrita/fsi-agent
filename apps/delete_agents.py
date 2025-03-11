import time
import streamlit as st
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from apps.jsondb import list_agents, list_threads, delete_agent, delete_thread

project_client = AIProjectClient.from_connection_string(
    conn_str=st.session_state.project_connection, credential=DefaultAzureCredential()
)

# Main UI
st.header("Delete Agent or Thread")

@st.dialog("Confirm Deletion")
def delete_agent_modal(type: str, details: str, agent_id: str):
    if type == "agent":
        st.info(f"Are you sure you want to delete the agent '{details}'?", icon="ℹ️")
        st.warning("Deleting an agent will also delete all associated threads.", icon="⚠️")
    else:
        st.info(f"Are you sure you want to delete the thread '{details}'?", icon="ℹ️")

    confirm = st.text_input(":red[**Type DELETE to proceed:**]")
    # agents = project_client.agents.list_agents()
    # st.write(agents)

    if st.button("Proceed", disabled=confirm != "DELETE"):
        with st.spinner("Deleting..."):
            try:
                if type == "agent":
                    # delete all threads associated with the agent
                    threads = list_threads(details)
                    for thread in threads:
                        project_client.agents.delete_thread(thread["id"])
                        delete_thread(thread["id"])
                    project_client.agents.delete_agent(agent_id)
                    delete_agent(agent_id)
                else:
                    project_client.agents.delete_thread(details)
                    delete_thread(details)
            except Exception as e:
                st.error(f"An error occurred: {e}")
                return

        st.info(f"{type} deleted!", icon="ℹ️")
        time.sleep(1)
        st.rerun()

agents = list_agents()
# create a list of agents names
agent_names = [agent["name"] for agent in agents]
agent_selected = st.selectbox(":blue[**Select an Agent:**]", agent_names, index=None, key="select_agent")

agent_id = agents[agent_names.index(agent_selected)]["id"] if agent_selected else None

# delete an agent
if st.button(":red[**⚙️Delete Agent**]", disabled=not agent_selected):
    delete_agent_modal("agent", agent_selected, agent_id)

# select an agent
if agent_selected:
    threads = list_threads(agent_id)
    # create a list of threads
    thread_ids = [thread["id"] for thread in threads]
    thread_selected = st.selectbox(":blue[**Select a Thread:**]", thread_ids, index=None, key="select_thread")

    # delete a thread
    if st.button(":red[**⚙️Delete Thread**]", disabled=not thread_selected):
        delete_agent_modal("thread", thread_selected, agent_id)
