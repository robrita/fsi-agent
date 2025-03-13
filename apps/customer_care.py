import streamlit as st
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import ToolSet, CodeInterpreterTool, FunctionTool, AzureAISearchTool, ConnectionType
from apps.user_functions import user_functions

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

@st.cache_resource
def create_agent():
    try:
        with st.spinner("Connecting..."):
            project_client = AIProjectClient.from_connection_string(
                conn_str=st.session_state.project_connection, credential=DefaultAzureCredential()
            )

            functions = FunctionTool(user_functions)
            code_interpreter = CodeInterpreterTool()

            # [START create_agent_with_azure_ai_search_tool]
            conn_list = project_client.connections.list()
            conn_id = ""
            for conn in conn_list:
                if conn.connection_type == ConnectionType.AZURE_AI_SEARCH:
                    print(f"Found Azure AI Search connection: {conn}")
                    conn_id = conn.id
                    break

            print(f"Connection ID: {conn_id}")

            # Initialize agent AI search tool and add the search index connection id
            ai_search = AzureAISearchTool(index_connection_id=conn_id, index_name="aiagent")

            toolset = ToolSet()
            toolset.add(functions)
            toolset.add(code_interpreter)
            toolset.add(ai_search)

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

        st.session_state.agent["id"] = agent.id
        return project_client

    except Exception as e:
        st.error(f"Error initializing agent: {str(e)}")
        st.stop()

def generate_response(prompt: str):
    """Generate response from Azure OpenAI"""
    try:
        message_placeholder = st.empty()

        if not st.session_state.client:
            st.session_state.client = create_agent()

        project_client = st.session_state.client
        # project_client = None

        # if not st.session_state.agent["id"]:
        #     project_client = create_agent()

        with st.spinner("Thinking..."):
            # functions = FunctionTool(user_functions)
            # code_interpreter = CodeInterpreterTool()

            # # [START create_agent_with_azure_ai_search_tool]
            # conn_list = project_client.connections.list()
            # conn_id = ""
            # for conn in conn_list:
            #     if conn.connection_type == ConnectionType.AZURE_AI_SEARCH:
            #         print(f"Found Azure AI Search connection: {conn}")
            #         conn_id = conn.id
            #         break

            # print(f"Connection ID: {conn_id}")

            # # Initialize agent AI search tool and add the search index connection id
            # ai_search = AzureAISearchTool(index_connection_id=conn_id, index_name="aiagent")

            # toolset = ToolSet()
            # toolset.add(functions)
            # toolset.add(code_interpreter)
            # toolset.add(ai_search)

            # # The CodeInterpreterTool needs to be included in creation of the agent so that it can be used
            # agent = project_client.agents.create_agent(
            #     model=st.session_state.agent["model"],
            #     name=st.session_state.agent["name"],
            #     top_p=st.session_state.agent["top_p"],
            #     temperature=st.session_state.agent["temperature"],
            #     description=st.session_state.agent["description"],
            #     instructions=st.session_state.agent["instructions"],
            #     toolset=toolset,
            # )

            # Create new thread for an existing agent
            if not st.session_state.thread_id:
                thread = project_client.agents.create_thread()
                st.session_state.thread_id = thread.id
                # delete the last agent and thread
                # project_client.agents.delete_thread(st.session_state.thread_id)
                # project_client.agents.delete_agent(st.session_state.agent["id"])

            print(f"agent ID: {st.session_state.agent["id"]}")
            print(f"thread ID: {st.session_state.thread_id}")

            # Create a message, with the prompt being the message content that is sent to the model
            message = project_client.agents.create_message(
                thread_id=st.session_state.thread_id,
                role="user",
                content=prompt,
            )
            print(f"Created message, message ID: {message.id}")

            # Run the agent to process tne message in the thread
            run = project_client.agents.create_and_process_run(thread_id=st.session_state.thread_id, assistant_id=st.session_state.agent["id"])
            print(f"Run finished with status: {run.status}")

            # Check if you got "Rate limit is exceeded.", then you want to increase the token limit
            if run.status == "failed":
                raise Exception(run.last_error)

        # Delete the assistant when done
        # project_client.agents.delete_agent(st.session_state.agent["id"])

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

        st.session_state.messages.append({"role": "assistant", "content": contents})

    except Exception as e:
        st.error(f"Error generating response: {str(e)}")
        print(f"Error generating response: {str(e)}")
        error_message = "I'm sorry, I encountered an error while processing your request. Please try again."
        message_placeholder.markdown(error_message)

        contents = [{"type": "text", "value": error_message}]
        st.session_state.messages.append({"role": "assistant", "content": contents})

# User input
if prompt := st.chat_input("Type your message here..."):
    # Display user message immediately
    st.chat_message("user", avatar=":material/person:").markdown(prompt)

    # Append user message to the session state
    contents = [{"type": "text", "value": prompt}]
    st.session_state.messages.append({"role": "user", "content": contents})

    # Generate and show AI response
    with st.chat_message("assistant", avatar="✨"):
        generate_response(prompt)
