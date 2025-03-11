import os
from typing import Any
from pathlib import Path
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import CodeInterpreterTool

load_dotenv() # Load environment variables from .env file

# Connecting to our Azure AI Foundry project, which will allow us to use the deployed gpt-4o model
project_connection_string = os.getenv("AIPROJECT_CONNECTION_STRING")
model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

project_client = AIProjectClient.from_connection_string(
    conn_str=project_connection_string, credential=DefaultAzureCredential()
)

# with project_client:
# Create an instance of the CodeInterpreterTool, which is responsible for generating the bar chart
code_interpreter = CodeInterpreterTool()

# The CodeInterpreterTool needs to be included in creation of the agent so that it can be used
agent = project_client.agents.create_agent(
    model=model,
    name="my-agent-barchart",
    instructions="You are a helpful agent.",
    tools=code_interpreter.definitions,
    tool_resources=code_interpreter.resources,
)
print(f"Created agent, agent ID: {agent["id"]}")

# Create a thread which is a conversation session between an agent and a user.
thread = project_client.agents.create_thread()
print(f"Created thread, thread ID: {thread.id}")

# Create a prompt which contains the data + details for how the agent should generate the bar chart
prompt = "Could you please create a bar chart for the using the following data and \
    provide the file to me? Name the file as health-plan-comparision.png. \
    Here is the data: \
    Provider	    Monthly Premium	Deductible	Out-of-Pocket Limit \
    Northwind	    $300		$1,500		$6,000 \
    Aetna		    $350		$1,000		$5,500 \
    United Health	$250		$2,000		$7,000 \
    Premera		    $200		$2,200		$6,500 \
"

# Create a message, with the prompt being the message content that is sent to the model
message = project_client.agents.create_message(
    thread_id=thread.id,
    role="user",
    content=prompt,
)
print(f"Created message, message ID: {message.id}")

# Run the agent to process tne message in the thread
run = project_client.agents.create_and_process_run(thread_id=thread.id, assistant_id=agent["id"])
print(f"Run finished with status: {run.status}")

if run.status == "failed":
    # Check if you got "Rate limit is exceeded.", then you want to increase the token limit
    print(f"Run failed: {run.last_error}")

# Get all messages from the thread
messages = project_client.agents.list_messages(thread_id=thread.id)
print(f"Messages: {messages}")

# Generate an image file for the bar chart
for file_path_annotation in messages.file_path_annotations:
    file_name = Path(file_path_annotation.text).name
    project_client.agents.save_file(file_id=file_path_annotation.file_path.file_id, file_name=file_name)
    print(f"Saved image file to: {Path.cwd() / file_name}")

# Delete the agent once done
project_client.agents.delete_agent(agent["id"])
project_client.agents.delete_thread(thread_id=thread.id)
print("Deleted agent")