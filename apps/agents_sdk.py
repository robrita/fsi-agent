from __future__ import annotations as _annotations
import os
import json
import asyncio
import random
import streamlit as st

from pydantic import BaseModel
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import ToolSet, CodeInterpreterTool, FunctionTool, AzureAISearchTool, ConnectionType
from apps.user_functions import user_functions
from openai import AsyncAzureOpenAI

from agents import (
    Agent,
    HandoffOutputItem,
    ItemHelpers,
    MessageOutputItem,
    RunContextWrapper,
    Runner,
    ToolCallItem,
    ToolCallOutputItem,
    TResponseInputItem,
    function_tool,
    handoff,
    OpenAIChatCompletionsModel,
)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

load_dotenv()

# Main UI
st.header('Customer Care Agent')

azure_client = AsyncAzureOpenAI(
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("MY_OPENAI_API_KEY"),
)

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

### CONTEXT


class TnGAgentContext(BaseModel):
    user_name: str | None = None
    last_4dig_num: str | None = None
    birth_date: str | None = None
    user_id: str | None = None


### TOOLS


@function_tool(
    name_override="faq_lookup_tool", description_override="Lookup frequently asked questions."
)
async def faq_lookup_tool(question: str) -> str:
    print(f"User Question: {question}")
    print(f"thread ID: {st.session_state.thread_id}")
    project_client = st.session_state.client

    try:
        # Create a message, with the prompt being the message content that is sent to the model
        project_client.agents.create_message(
            thread_id=st.session_state.thread_id,
            role="user",
            content=question,
        )

        # Run the agent to process tne message in the thread
        run = project_client.agents.create_and_process_run(thread_id=st.session_state.thread_id, agent_id="asst_q85dqNdBIJxzugnWxC1YsZgx")
        print(f"Run finished with status: {run.status}")

        # Check if you got "Rate limit is exceeded.", then you want to increase the token limit
        if run.status == "failed":
            raise Exception(run.last_error)

        # Get all messages from the thread
        messages = project_client.agents.list_messages(st.session_state.thread_id)
        last_msg = messages.get_last_text_message_by_role("assistant")

        print(f"Last message: {last_msg.text.value}")
        return last_msg.text.value

    except Exception as e:
        print(f"Error: {e}")
        return "I'm sorry, I encountered an error while processing your request. Please try again."


@function_tool
async def update_user_name(
    context: RunContextWrapper[TnGAgentContext], user_name: str, last_4dig_num: str, birth_date: str,
) -> str:
    """
    Update the customer user name for a given last 4 digits of id and birth date.

    Args:
        user_name: The new customer user name.
        last_4dig_num: The last 4 digits of customer account number.
        birth_date: The customer birth date.
    """
    # Update the context based on the customer's input
    context.context.user_name = user_name
    context.context.last_4dig_num = last_4dig_num
    context.context.birth_date = birth_date

    # Ensure that the flight number has been set by the incoming handoff
    assert context.context.user_id is not None, "User ID is required"
    return f"Updated user name to {user_name}"


### HOOKS


async def on_seat_booking_handoff(context: RunContextWrapper[TnGAgentContext]) -> None:
    user_id = f"FLT-{random.randint(100, 999)}"
    context.context.user_id = user_id


### AGENTS

faq_agent = Agent[TnGAgentContext](
    name="FAQ Agent",
    handoff_description="A helpful agent that can answer questions about TnG Digital.",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
    You are an FAQ agent. If you are speaking to a customer, you probably were transferred to from the triage agent.
    Use the following routine to support the customer.
    # Routine
    1. Identify the last question asked by the customer.
    2. Use the faq lookup tool to answer the question. Do not rely on your own knowledge.
    3. If you cannot answer the question, transfer back to the triage agent.""",
    tools=[faq_lookup_tool],
    model=OpenAIChatCompletionsModel(
        model="gpt-4o",
        openai_client=azure_client,
    ),
)

account_management_agent = Agent[TnGAgentContext](
    name="Account Management Agent",
    handoff_description="A helpful agent that can update customer user name.",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
    You are an account management agent. If you are speaking to a customer, you probably were transferred to from the triage agent.
    Use the following routine to support the customer.
    # Routine
    1. Ask for their new user name.
    2. Ask the last 4 digits of user's account number.
    3. Ask the user's birth date.
    If the customer asks a question that is not related to the routine, transfer back to the triage agent. """,
    tools=[update_user_name],
    model=OpenAIChatCompletionsModel(
        model="gpt-4o",
        openai_client=azure_client,
    ),
)

triage_agent = Agent[TnGAgentContext](
    name="Triage Agent",
    handoff_description="A triage agent that can delegate a customer's request to the appropriate agent.",
    instructions=(
        f"{RECOMMENDED_PROMPT_PREFIX} "
        f"{st.session_state.agent["instructions"]}"
    ),
    handoffs=[
        handoff(agent=account_management_agent, on_handoff=on_seat_booking_handoff),
        faq_agent,
    ],
    model=OpenAIChatCompletionsModel(
        model="gpt-4o",
        openai_client=azure_client,
    ),
)

faq_agent.handoffs.append(triage_agent)
account_management_agent.handoffs.append(triage_agent)


### AZURE AI AGENTS

def create_agent():
    try:
        with st.spinner("Loading..."):
            project_client = AIProjectClient.from_connection_string(
                conn_str=st.session_state.project_connection, credential=DefaultAzureCredential()
            )

            # Create new thread for an existing agent
            thread = project_client.agents.create_thread()
            st.session_state.thread_id = thread.id

            if "function_tool" in st.session_state.agent["tools"]:
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
                last_info = {}

                # delete the last agent and thread
                with open("apps/last_info.json", "r") as f:
                    last_info = json.load(f)
                    if last_info["thread_id"]:
                        project_client.agents.delete_thread(last_info["thread_id"])

                    if last_info["agent_id"]:
                        project_client.agents.delete_agent(last_info["agent_id"])

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
                print(f"agent ID: {agent.id}")

                # Save a new agent id and thread id to a file
                with open("apps/last_info.json", "w") as f:
                    last_info["thread_id"] = thread.id
                    last_info["agent_id"] = agent.id
                    json.dump(last_info, f, indent=4)

            return project_client

    except Exception as e:
        st.error(f"Error initializing agent: {str(e)}")
        st.stop()


def log_message(
    canvas,
    content: str,
    role: str,
) -> None:
    canvas.markdown(content)
    contents = [{"type": "text", "value": content}]
    st.session_state.messages.append({"role": role, "content": contents})


### RUN

if "current_agent" not in st.session_state:
    current_agent: Agent[TnGAgentContext] = triage_agent
    st.session_state.current_agent = current_agent

if "input_items" not in st.session_state:
    input_items: list[TResponseInputItem] = []
    st.session_state.input_items = input_items

if not st.session_state.client:
    st.session_state.client = create_agent()

if "user_auth" not in st.session_state:
    st.session_state.user_auth = None
    with st.chat_message("assistant", avatar="✨"):
        log_message(st, "Plase enter your OTP", "assistant")

async def main(user_input: str) -> None:
    current_agent = st.session_state.current_agent
    input_items = st.session_state.input_items
    context = TnGAgentContext()
    message_placeholder = st.empty()
    last_response = None

    try:
        with st.spinner("Thinking..."):
            input_items.append({"content": user_input, "role": "user"})
            result = await Runner.run(current_agent, input_items, context=context)

            for new_item in result.new_items:
                agent_name = new_item.agent.name
                if isinstance(new_item, MessageOutputItem):
                    last_response = f"[{agent_name}] {ItemHelpers.text_message_output(new_item)}"
                    print(last_response)
                elif isinstance(new_item, HandoffOutputItem):
                    print(
                        f"Handed off from {new_item.source_agent.name} to {new_item.target_agent.name}"
                    )
                elif isinstance(new_item, ToolCallItem):
                    print(f"{agent_name}: Calling a tool")
                elif isinstance(new_item, ToolCallOutputItem):
                    print(f"{agent_name}: Tool call output: {new_item.output}")
                else:
                    print(f"{agent_name}: Skipping item: {new_item.__class__.__name__}")

            st.session_state.input_items = result.to_input_list()
            st.session_state.current_agent = result.last_agent

    except Exception as e:
        print(f"Error: {e}")
        last_response = "I'm sorry, I encountered an error while processing your request. Please try again."

    log_message(message_placeholder, last_response, "assistant")


# User input
if user_input := st.chat_input("Type your message here..."):
    # Display user message immediately
    with st.chat_message("user", avatar=":material/person:"):
        log_message(st, user_input, "user")

    # Generate and show AI response
    with st.chat_message("assistant", avatar="✨"):
        if not st.session_state.user_auth:
            if user_input == "123456":
                st.session_state.user_auth = True
                log_message(st, "OTP verified successfully! How can I help you today?", "assistant")
            else:
                st.session_state.user_auth = False
                log_message(st, "Please enter your OTP again", "assistant")
        else:
            asyncio.run(main(user_input))
