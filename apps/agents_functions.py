import streamlit as st
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import ToolSet, CodeInterpreterTool, FunctionTool
from apps.jsondb import save_thread, update_thread
from apps.user_functions import user_functions

project_client = AIProjectClient.from_connection_string(
    conn_str=st.session_state.project_connection, credential=DefaultAzureCredential()
)

# Main UI
st.header('Customer Care Agent')

# Display chat messages
for message in st.session_state.messages:
    if message["role"] == "user":
        st.chat_message(message["role"], avatar=":material/person:").markdown(message["content"][0]["value"])
    else:
        with st.chat_message(message["role"], avatar="✨"):
            for content in message["content"]:
                if content["type"] == "text":
                    st.markdown(content["value"])
                else:
                    st.image(f"apps/{content['value']}")

def generate_response(prompt: str):
    """Generate response from Azure OpenAI"""
    try:
        functions = FunctionTool(user_functions)
        code_interpreter = CodeInterpreterTool()

        toolset = ToolSet()
        toolset.add(functions)
        toolset.add(code_interpreter)

        # The CodeInterpreterTool needs to be included in creation of the agent so that it can be used
        agent = project_client.agents.create_agent(
            model=st.session_state.agent["model"],
            name=st.session_state.agent["name"],
            top_p=st.session_state.agent["top_p"],
            temperature=st.session_state.agent["temperature"],
            description=st.session_state.agent["description"],
            instructions=st.session_state.agent["instructions"],
            toolset=toolset,
        )

        # Create new thread for an existing agent
        if not st.session_state.thread_id:
            thread = project_client.agents.create_thread()
            st.session_state.thread_id = thread.id
            st.session_state.messages = []
            save_thread()

        print(f"agent ID: {agent.id}")
        print(f"thread ID: {st.session_state.thread_id}")

        message_placeholder = st.empty()
        contents = [{"type": "text", "value": prompt}]

        update_thread("user", contents)
        st.session_state.messages.append({"role": "user", "content": contents})

        with st.spinner("Thinking..."):
            # Create a message, with the prompt being the message content that is sent to the model
            message = project_client.agents.create_message(
                thread_id=st.session_state.thread_id,
                role="user",
                content=prompt,
            )
            print(f"Created message, message ID: {message.id}")

            # Run the agent to process tne message in the thread
            run = project_client.agents.create_and_process_run(thread_id=st.session_state.thread_id, assistant_id=agent.id)
            print(f"Run finished with status: {run.status}")

            # Check if you got "Rate limit is exceeded.", then you want to increase the token limit
            if run.status == "failed":
                raise Exception(run.last_error)

        # Delete the assistant when done
        project_client.agents.delete_agent(agent.id)

        # Get all messages from the thread
        messages = project_client.agents.list_messages(st.session_state.thread_id)
        contents = []

        last_msg = messages.get_last_text_message_by_role("assistant")
        print(last_msg)

        message_placeholder.markdown(last_msg.text.value)
        contents.append({
            "type": last_msg.type,
            "value": last_msg.text.value
        })

        update_thread("assistant", contents)
        st.session_state.messages.append({"role": "assistant", "content": contents})

    except Exception as e:
        st.error(f"Error generating response: {str(e)}")
        print(f"Error generating response: {str(e)}")
        error_message = "I'm sorry, I encountered an error while processing your request. Please try again."
        message_placeholder.markdown(error_message)

        contents = [{"type": "text", "value": error_message}]
        update_thread("assistant", contents)
        st.session_state.messages.append({"role": "assistant", "content": contents})

# User input
if st.session_state.agent["name"]:
    if prompt := st.chat_input("Type your message here..."):
        # Display user message immediately
        st.chat_message("user", avatar=":material/person:").markdown(prompt)

        # Generate and show AI response
        with st.chat_message("assistant", avatar="✨"):
            generate_response(prompt)
