import streamlit as st
from pathlib import Path
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import ToolSet, ConnectionType, CodeInterpreterTool, AzureAISearchTool, FunctionTool, FileSearchTool, BingGroundingTool, AzureFunctionTool, OpenApiTool, OpenApiAnonymousAuthDetails
from apps.jsondb import save_agent, save_thread, update_thread

project_client = AIProjectClient.from_connection_string(
    conn_str=st.session_state.project_connection, credential=DefaultAzureCredential()
)

# Main UI
agent_name = st.session_state.agent["name"] or "Select an agent"
st.header(agent_name)

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
        if not st.session_state.agent["id"]:
            toolset = ToolSet()
            headers = {}

            # Add tools to the toolset
            if "code_interpreter" in st.session_state.agent["tools"]:
                code_interpreter = CodeInterpreterTool()
                toolset.add(code_interpreter)

            if "ai_search" in st.session_state.agent["tools"]:
                conn_list = project_client.connections.list()
                conn_id = ""
                for conn in conn_list:
                    if conn.connection_type == ConnectionType.AZURE_AI_SEARCH:
                        conn_id = conn.id
                        break
                ai_search = AzureAISearchTool(index_connection_id=conn_id, index_name="myindexname")
                toolset.add(ai_search)

            if "functions" in st.session_state.agent["tools"]:
                functions = FunctionTool(st.session_state.agent["tools"]["user_functions"])
                toolset.add(functions)

            if "file_search_tool" in st.session_state.agent["tools"]:
                file_search_tool = FileSearchTool(vector_store_ids=st.session_state.agent["tools"]["vector_store_ids"])
                toolset.add(file_search_tool)

            if "bing" in st.session_state.agent["tools"]:
                bing_connection = project_client.connections.get(connection_name=st.session_state.agent["tools"]["bing"])
                bing = BingGroundingTool(connection_id=bing_connection.id)
                toolset.add(bing)
                headers={"x-ms-enable-preview": "true"}

            if "azure_function_tool" in st.session_state.agent["tools"]:
                azure_function_tool = AzureFunctionTool(st.session_state.agent["tools"]["azure_function_tool"])
                toolset.add(azure_function_tool)

            if "openapi_tool" in st.session_state.agent["tools"]:
                auth = OpenApiAnonymousAuthDetails()
                # Initialize agent OpenApi tool using the read in OpenAPI spec
                openapi_tool = OpenApiTool(
                    name="get_weather", spec=st.session_state.agent["tools"].openapi_tool[0], description="Retrieve weather information for a location", auth=auth
                )
                openapi_tool.add_definition(
                    name="get_countries", spec=st.session_state.agent["tools"].openapi_tool[1], description="Retrieve a list of countries", auth=auth
                )
                openapi_tool = FunctionTool(st.session_state.agent["tools"]["user_functions"])
                toolset.add(openapi_tool)

            # The CodeInterpreterTool needs to be included in creation of the agent so that it can be used
            agent = project_client.agents.create_agent(
                model=st.session_state.agent["model"],
                name=st.session_state.agent["name"],
                top_p=st.session_state.agent["top_p"],
                temperature=st.session_state.agent["temperature"],
                description=st.session_state.agent["description"],
                instructions=st.session_state.agent["instructions"],
                toolset=toolset,
                headers=headers
            )

            # Create a thread which is a conversation session between an agent and a user.
            thread = project_client.agents.create_thread()
            st.session_state.thread_id = thread.id
            st.session_state.agent["id"] = agent["id"]
            st.session_state.messages = []

            # Save agent and thread to database
            save_agent()
            save_thread()
            print(f"Created agent, agent ID: {st.session_state.agent["id"]}")
            print(f"Created thread, thread ID: {st.session_state.thread_id}")
        else:
            print(f"agent ID: {st.session_state.agent["id"]}")
            print(f"thread ID: {st.session_state.thread_id}")

        # Create new thread for an existing agent
        if not st.session_state.thread_id:
            thread = project_client.agents.create_thread()
            st.session_state.thread_id = thread.id
            save_thread()

        # # Create a prompt which contains the data + details for how the agent should generate the bar chart
        # prompt = "Could you please create a bar chart for the using the following data and \
        #     provide the file to me? Name the file as health-plan-comparision.png. \
        #     Here is the data: \
        #     Provider	    Monthly Premium	Deductible	Out-of-Pocket Limit \
        #     Northwind	    $300		$1,500		$6,000 \
        #     Aetna		    $350		$1,000		$5,500 \
        #     United Health	$250		$2,000		$7,000 \
        #     Premera		    $200		$2,200		$6,500 \
        # "
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
            run = project_client.agents.create_and_process_run(thread_id=st.session_state.thread_id, assistant_id=st.session_state.agent["id"])
            print(f"Run finished with status: {run.status}")

            # Check if you got "Rate limit is exceeded.", then you want to increase the token limit
            if run.status == "failed":
                raise Exception(run.last_error)

        # Get all messages from the thread
        messages = project_client.agents.list_messages(st.session_state.thread_id)
        contents = []

        for cont in messages.data[0].content:
            if cont.type == "text":
                message_placeholder.markdown(cont.text.value)
                contents.append({
                    "type": cont.type,
                    "value": cont.text.value
                })
            elif cont.type == "image_file":
                file_name = f"apps/{cont.image_file.file_id}.jpg"
                project_client.agents.save_file(cont.image_file.file_id, file_name)

                message_placeholder.image(f"apps/{message['value']}.jpg")
                contents.append({
                    "type": cont.type,
                    "value": cont.image_file.file_id
                })

        update_thread("assistant", contents)
        st.session_state.messages.append({"role": "assistant", "content": contents})
        print(messages.data[0].content)

        # # Generate an image file for the bar chart
        # for file_path_annotation in messages.file_path_annotations:
        #     file_name = Path(file_path_annotation.text).name
        #     project_client.agents.save_file(file_id=file_path_annotation.file_path.file_id, file_name=file_name)
        #     print(f"Saved image file to: {Path.cwd() / file_name}")

        # # Delete the agent once done
        # project_client.agents.delete_agent(st.session_state.agent["id"])
        # project_client.agents.delete_thread(st.session_state.thread_id)
        # print("Deleted agent")
    except Exception as e:
        st.error(f"Error generating response: {str(e)}")
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
