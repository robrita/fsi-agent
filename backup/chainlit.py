import os
import chainlit as cl
import datetime
import logging
from azure.cosmos import CosmosClient
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Disable verbose connection logs
logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
logger.setLevel(logging.WARNING)

# Azure OpenAI Configuration
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

# Azure CosmosDB Configuration
cosmos_endpoint = os.getenv("COSMOS_ENDPOINT")
cosmos_key = os.getenv("COSMOS_KEY")
cosmos_database_name = os.getenv("COSMOS_DATABASE", "chathistory")
cosmos_container_name = os.getenv("COSMOS_CONTAINER", "conversations")

# Initialize CosmosDB client
cosmos_client = CosmosClient(cosmos_endpoint, credential=cosmos_key)
database = cosmos_client.get_database_client(cosmos_database_name)
container = database.get_container_client(cosmos_container_name)

# Chat history functions
def save_chat_to_cosmos(session_id, user_message, assistant_message):
    try:
        timestamp = datetime.datetime.now().isoformat()
        chat_item = {
            "id": f"{session_id}_{timestamp}",
            "session_id": session_id,
            "timestamp": timestamp,
            "user_message": user_message,
            "assistant_message": assistant_message
        }
        container.create_item(body=chat_item)
        return True
    except Exception as e:
        print(f"Error saving chat to CosmosDB: {str(e)}")
        return False

def get_chat_history(session_id, limit=5):
    try:
        query = f"SELECT * FROM c WHERE c.session_id = '{session_id}' ORDER BY c.timestamp DESC OFFSET 0 LIMIT {limit}"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        # Return in chronological order
        return list(reversed(items))
    except Exception as e:
        print(f"Error retrieving chat history: {str(e)}")
        return []

# Chainlit setup
@cl.on_chat_start
async def on_chat_start():
    # Store session information
    session_id = cl.user_session.get("id")
    
    # Set up the initial message
    await cl.Message(
        content="Hello! I'm your AI assistant powered by Azure OpenAI GPT-4o. How can I help you today?"
    ).send()
    
    # Initialize chat history if it exists
    chat_history = get_chat_history(session_id)
    if (chat_history):
        cl.user_session.set("chat_history", chat_history)
        
        # Display previous messages
        for chat in chat_history:
            await cl.Message(content=chat["user_message"], author="User").send()
            await cl.Message(content=chat["assistant_message"]).send()
    else:
        cl.user_session.set("chat_history", [])

@cl.on_message
async def on_message(message: cl.Message):
    session_id = cl.user_session.get("id")
    user_message = message.content

    # Create the messages for OpenAI API
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant for financial services. Provide clear, accurate, and concise information."}
    ]
    
    # Add chat history to provide context
    chat_history = get_chat_history(session_id)
    for chat in chat_history[-5:]:  # Limit to last 5 conversations to avoid token limits
        messages.append({"role": "user", "content": chat["user_message"]})
        messages.append({"role": "assistant", "content": chat["assistant_message"]})
    
    # Add the current user message
    messages.append({"role": "user", "content": user_message})
    
    # Call Azure OpenAI API
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.7,
            max_tokens=800,
            stream=True
        )
        
        # Process streaming response
        content_msg = cl.Message(content="")
        await content_msg.send()
        
        full_response = ""
        # Properly iterate over streaming response without using async for
        for chunk in response:
            # Add error checking to handle empty choices list
            if hasattr(chunk, 'choices') and len(chunk.choices) > 0 and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                await content_msg.stream_token(content)
        
        await content_msg.update()
        
        # Save conversation to CosmosDB
        save_chat_to_cosmos(session_id, user_message, full_response)
        
    except Exception as e:
        await cl.Message(content=f"Error: {str(e)}").send()

if __name__ == "__main__":
    # Chainlit will automatically run the application
    pass
