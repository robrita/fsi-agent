import json
import streamlit as st
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

project_client = AIProjectClient.from_connection_string(
    conn_str=st.session_state.project_connection, credential=DefaultAzureCredential()
)

# Main UI
st.header("Health Care Planner Agent")

with open("data/task_chains.json", "r") as f:
    tasks = json.load(f)

def generate_response(user_input: str):
    """Generate response from Azure OpenAI"""
    try:
        # message_placeholder = st.empty()
        last_response = ""

        # loop through the tasks
        for task in tasks:
            # ----- Agent 1: Document Search Agent -----
            content = task["user_query"].replace("{user_input}", user_input).replace("{last_response}", last_response)
            st.chat_message("user", avatar=":material/person:").markdown(f"[{task["agent_name"]}] {content}")

            thread1 = project_client.agents.create_thread()

            with st.spinner("Thinking..."):
                # Create a message, with the prompt being the message content that is sent to the model
                project_client.agents.create_message(thread_id=thread1.id, role="user", content=content)
                print(f">>>>> Created message: {content}")
                st.toast(f"Message sent: {content}", icon="✅")

                # Run the agent to process tne message in the thread
                run = project_client.agents.create_and_process_run(thread_id=thread1.id, assistant_id=task["agent_id"])

                # Check if you got "Rate limit is exceeded.", then you want to increase the token limit
                if run.status == "failed":
                    raise Exception(run.last_error)

            # Get all messages from the thread
            messages = project_client.agents.list_messages(thread1.id)
            last_msg = messages.get_last_text_message_by_role("assistant")

            last_response = last_msg.text.value
            st.chat_message("assistant", avatar="✨").markdown(f"[{task["agent_name"]}] {last_response}")

            print(f">>>>> Last Response: {last_response}")
            st.toast(f"Last Response", icon="✅")

            if task["break_status"] and task["break_status"] == last_response:
                break

    except Exception as e:
        st.error(f"Error generating response: {str(e)}")
        error_message = "I'm sorry, I encountered an error while processing your request. Please try again."
        st.chat_message("assistant", avatar="🚫").markdown(error_message)

# User input
if prompt := st.chat_input("Type your message here..."):
    # # Display user message immediately
    # st.chat_message("user", avatar=":material/person:").markdown(prompt)

    # # Generate and show AI response
    # with st.chat_message("assistant", avatar="✨"):
    generate_response(prompt)
