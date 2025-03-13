from fastapi import FastAPI, HTTPException, status
import httpx
import os
import logging
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file if it exists

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.post("/chat/completions")
async def chat_completions(request: dict):
    # Set up headers for the request
    headers = {
        "Content-Type": "application/json",
        "api-key": os.getenv("AZURE_OPENAI_API_KEY")
    }
    
    try:
        # Make the request to Azure OpenAI with a timeout
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url=os.getenv("AZURE_OPENAI_URI"),
                headers=headers,
                json=request
            )
            
            # Raise exception for any HTTP error status
            response.raise_for_status()
            
            # Return the response from Azure OpenAI
            return response.json()
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error occurred: {str(e)}"
        )
