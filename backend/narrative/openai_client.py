"""OpenAI client with retry logic for API calls."""
import asyncio
import random
from typing import Dict, List, Any

class OpenAIClient:
    """Wrapper for OpenAI client with retry logic."""
    
    def __init__(self, client, max_retries=3, base_retry_delay=5):
        """Initialize the OpenAI client wrapper.
        
        Args:
            client: AsyncOpenAI client instance
            max_retries: Maximum number of retries for API calls
            base_retry_delay: Base delay between retries in seconds
        """
        self.client = client
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
    
    async def call_with_retry(self, model, messages, response_format, max_completion_tokens):
        """Make an OpenAI API call with retry logic for rate limits and other errors.
        
        Args:
            model: The model to use (e.g., "o1")
            messages: List of message objects to send to the API
            response_format: Format specification for the response
            max_completion_tokens: Maximum tokens to generate in the completion
            
        Returns:
            The API response object
            
        Raises:
            Exception: If all retries fail
        """
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format=response_format,
                    max_completion_tokens=max_completion_tokens
                )
                return response
            except Exception as e:
                error_message = str(e)
                print(f"API call error (attempt {attempt+1}/{self.max_retries}): {error_message}")
                
                # Check for rate limit errors
                if "rate_limit_exceeded" in error_message or "rate limit" in error_message.lower():
                    # Exponential backoff with jitter
                    retry_delay = self.base_retry_delay * (2 ** attempt) + random.uniform(0, 2)
                    print(f"Rate limit exceeded. Retrying in {retry_delay:.2f} seconds...")
                    await asyncio.sleep(retry_delay)
                    continue
                # Check for context length errors - these shouldn't be retried
                elif "context_length_exceeded" in error_message:
                    print("Context length exceeded. Cannot retry with same parameters.")
                    raise
                # Other errors - retry after a short delay
                elif attempt < self.max_retries - 1:
                    retry_delay = self.base_retry_delay + random.uniform(0, 2)
                    print(f"API error. Retrying in {retry_delay:.2f} seconds...")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    # Last attempt failed, propagate the error
                    raise
        
        # If we get here, all retries failed
        raise Exception(f"API call failed after {self.max_retries} retries") 