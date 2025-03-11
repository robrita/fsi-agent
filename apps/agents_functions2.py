import os
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import FunctionTool, ToolSet, CodeInterpreterTool
from user_functions import user_functions
from pprint import pformat
from dotenv import load_dotenv

load_dotenv()

project_client = AIProjectClient.from_connection_string(
    credential=DefaultAzureCredential(),
    conn_str=os.environ["AIPROJECT_CONNECTION_STRING"],
)

with project_client:
    # Initialize agent toolset with user functions and code interpreter
    # [START create_agent_toolset]
    functions = FunctionTool(user_functions)
    code_interpreter = CodeInterpreterTool()

    toolset = ToolSet()
    toolset.add(functions)
    toolset.add(code_interpreter)

    agent = project_client.agents.create_agent(
        model="gpt-4o",
        name="my-agent",
        instructions="You are a helpful assistant",
        toolset=toolset,
    )
    # [END create_agent_toolset]
    print(f"Created agent, ID: {agent.id}")

    # Create thread for communication
    thread = project_client.agents.create_thread()
    print(f"Created thread, ID: {thread.id}")

    # Create message to thread
    message = project_client.agents.create_message(
        thread_id=thread.id,
        role="user",
        content="Hello, send an email with the datetime and weather information in New York?",
    )
    print(f"Created message, ID: {message.id}")

    # Create and process agent run in thread with tools
    # [START create_and_process_run]
    run = project_client.agents.create_and_process_run(
        thread_id=thread.id, assistant_id=agent.id)
    # [END create_and_process_run]
    print(f"Run finished with status: {run.status}")

    if run.status == "failed":
        print(f"Run failed: {run.last_error}")

    # Delete the assistant when done
    project_client.agents.delete_agent(agent.id)
    print("Deleted agent")

    # Fetch and log all messages
    messages = project_client.agents.list_messages(thread_id=thread.id)
    print("\n=== Thread Messages ===")
    print(pformat(messages.__dict__, indent=2, width=80))