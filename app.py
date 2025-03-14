from __future__ import annotations as _annotations
import os
import logging
import asyncio
import random
import chainlit as cl

from pydantic import BaseModel
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
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
    set_tracing_disabled,
)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

load_dotenv()
# Disable verbose connection logs
logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
logger.setLevel(logging.WARNING)
set_tracing_disabled(True)

azure_client = AsyncAzureOpenAI(
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("MY_OPENAI_API_KEY"),
)


class TnGAgentContext(BaseModel):
    user_name: str | None = None
    image_path: str | None = None
    birth_date: str | None = None
    user_id: str | None = None
    error_count: int = 0  # Track errors


### TOOLS


@function_tool(
    name_override="faq_lookup_tool", description_override="Lookup frequently asked questions."
)
async def faq_lookup_tool(question: str) -> str:
    print(f"User Question: {question}")
    project_client = cl.user_session.get("client")
    agent_id="asst_q85dqNdBIJxzugnWxC1YsZgx"

    try:
        # create thread for the agent
        thread = project_client.agents.create_thread()
        print(f"thread ID: {thread.id}")

        # Create a message, with the prompt being the message content that is sent to the model
        project_client.agents.create_message(
            thread_id=thread.id,
            role="user",
            content=question,
        )

        # Run the agent to process tne message in the thread
        run = project_client.agents.create_and_process_run(thread_id=thread.id, agent_id=agent_id)
        print(f"Run finished with status: {run.status}")

        # Check if you got "Rate limit is exceeded.", then you want to increase the token limit
        if run.status == "failed":
            raise Exception(run.last_error)

        # Get all messages from the thread
        messages = project_client.agents.list_messages(thread.id)
        last_msg = messages.get_last_text_message_by_role("assistant")

        # Delete the thread after processing
        if cl.user_session.get("delete_thread"):
            project_client.agents.delete_thread(thread.id)

        print(f"Last message: {last_msg.text.value}")
        return last_msg.text.value

    except Exception as e:
        print(f"Error: {e}")
        return "I'm sorry, I encountered an error while processing your request. Please try again."


@function_tool
async def update_user_name(
    context: RunContextWrapper[TnGAgentContext], user_name: str, image_path: str, birth_date: str,
) -> str:
    """
    Update the customer user name using government ID or passport image and birth date.

    Args:
        user_name: The new customer user name.
        image_path: image file path of government ID or passport.
        birth_date: The customer birth date.
    """
    # Update the context
    context.context.user_name = user_name
    context.context.image_path = image_path
    context.context.birth_date = birth_date
    print(f"Context context: {context.context}")

    # Ensure that the user ID has been set by the incoming handoff
    assert context.context.user_id is not None, "User ID is required"
    return f"Updated user name to {user_name}. ID image saved successfully."


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
    2. Ask for an image of their government ID or passport to be uploaded.
    3. Ask the user's birth date.
    If the customer asks a question that is not related to the routine, transfer back to the triage agent. """,
    tools=[update_user_name],
    model=OpenAIChatCompletionsModel(
        model="gpt-4o",
        openai_client=azure_client,
    ),
)

live_agent = Agent[TnGAgentContext](
    name="Live Agent",
    handoff_description="A live human agent that can handle complex issues or when a user specifically requests human assistance.",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
    You are a human customer service representative named Sarah. Act as if you are a real person, not an AI.
    Use a conversational, friendly tone and occasionally add small human touches to your responses.
    
    You should handle:
    1. Complex issues that other agents couldn't resolve
    2. Situations where a user has asked the same question multiple times
    3. When a user explicitly asks to speak with a human agent
    4. Technical errors or issues within the application
    
    # Human touches you can incorporate:
    - Mention taking notes: "Let me note that down for you"
    - Reference checking systems: "Let me check our system for that information"
    - Personalize responses: "I understand how frustrating that can be"
    - Occasionally mention your "team" or "colleagues"
    
    If the customer's issue is resolved or is actually simple enough for the automated system to handle,
    you can transfer them back to the triage agent.""",
    tools=[],
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
        "You are a helpful triaging agent. You can use your tools to delegate questions to other appropriate agents."
        "Use the response from other agents to answer the question. Do not rely on your own knowledge."
        "Other than greetings, do not answer any questions yourself."
        "If a user explicitly asks for a human agent or live support, transfer them to the Live Agent."
        "If a user is asking the same question more than two times, transfer them to the Live Agent."
    ),
    handoffs=[
        handoff(agent=account_management_agent, on_handoff=on_seat_booking_handoff),
        faq_agent,
        live_agent,
    ],
    model=OpenAIChatCompletionsModel(
        model="gpt-4o",
        openai_client=azure_client,
    ),
)

faq_agent.handoffs.append(triage_agent)
account_management_agent.handoffs.append(triage_agent)
live_agent.handoffs.append(triage_agent)


### AZURE AI PROJECT CLIENT

async def init_project():
    try:
        project_client = AIProjectClient.from_connection_string(
            conn_str=os.getenv("AIPROJECT_CONNECTION_STRING"), credential=DefaultAzureCredential()
        )

        # Create threads object in case it needs to persist across messages
        cl.user_session.set("threads", {})
        cl.user_session.set("delete_thread", True)

        return project_client

    except Exception as e:
        await cl.Error(content=f"Error initializing ai project: {str(e)}").send()


async def main(user_input: str) -> None:
    current_agent = cl.user_session.get("current_agent")
    input_items = cl.user_session.get("input_items")
    context = cl.user_session.get("context")

    last_response = None
    print(f"Received message: {user_input}")

    try:
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

        cl.user_session.set("current_agent", result.last_agent)
        cl.user_session.set("input_items", result.to_input_list())

    except Exception as e:
        print(f"Error: {e}")
        # Track errors and transfer to live agent if needed
        context.error_count += 1
        last_response = "I'm sorry, I encountered an error while processing your request. Please try again."
        
        if context.error_count >= 2:
            # Switch to live agent after multiple errors
            cl.user_session.set("current_agent", live_agent)
            last_response += " I'm transferring you to a live agent who can better assist you."

    # show the last response in the UI
    await cl.Message(last_response).send()


# Chainlit setup
@cl.on_chat_start
async def on_chat_start():
    # Set up the initial message
    await cl.Message("Plase enter your OTP to proceed.").send()

    # Initialize user session
    cl.user_session.set("user_auth", False)

    current_agent: Agent[TnGAgentContext] = triage_agent
    input_items: list[TResponseInputItem] = []

    cl.user_session.set("current_agent", current_agent)
    cl.user_session.set("input_items", input_items)

    cl.user_session.set("context", TnGAgentContext())
    cl.user_session.set("client", await init_project())


@cl.on_message
async def on_message(message: cl.Message):
    user_input = message.content

    for element in message.elements:
        # check if the element is an image
        if element.mime in ["image/jpeg", "image/png"]:
            user_input += f"\n[uploaded image] {element.path}"
            print(f"Received file: {element.path}")

    if cl.user_session.get("user_auth") is False:
        if user_input == "123456":
            cl.user_session.set("user_auth", True)
            await cl.Message("OTP verified successfully! How can I help you today?").send()
        else:
            await cl.Message("Please enter your OTP again").send()
    else:
        asyncio.run(main(user_input))

