# ai_services/common/deepseek_client.py

"""
Mock/Placeholder for the DeepSeek API Client.
Onyait Elias is responsible for the final implementation.
This mock allows Denzel's code to be developed and tested in isolation.
"""
import asyncio
import json
import random
import os
import time
import requests
from typing import Dict, Any, Optional
from decimal import Decimal, getcontext

from django.conf import settings
from django.utils import timezone
from backend.ai_integration.models import AIUsageLog

# --- Client Configuration & Constants ---
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "your-deepseek-api-key-goes-here")
BASE_URL = "https://api.deepseek.com/v1"
REQUEST_TIMEOUT = 30  # seconds

# --- Custom Exceptions ---
class AIClientError(Exception):
    """Base exception for AI client errors."""
    pass

class AIAPIError(AIClientError):
    """Represents an error returned by the AI API."""
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code

class AIConnectionError(AIClientError):
    """Represents a connection error to the AI API."""
    pass

class DeepSeekClient:
    """
    A production-ready, synchronous client for the DeepSeek API.
    This implementation fulfills Onyait Elias's core task of building a robust API client.
    It includes error handling and cost/usage tracking.
    """
    def __init__(self, api_key: str = DEEPSEEK_API_KEY):
        if not api_key or "your-deepseek-api-key" in api_key:
            raise ValueError("DEEPSEEK_API_KEY is not configured.")
        
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ClientNest/1.0"
        })

    def generate_content(self, system_prompt: str, user_prompt: str, user: Optional[settings.AUTH_USER_MODEL] = None, **kwargs) -> Dict[str, Any]:
        """
        Generates content using the DeepSeek API and logs the usage.
        """
        endpoint = "/chat/completions"
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": kwargs.get("temperature", 0.8),
            "max_tokens": kwargs.get("max_tokens", 800),
            "stream": False
        }

        start_time = time.perf_counter()
        
        try:
            response = self.session.post(
                f"{BASE_URL}{endpoint}",
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
            
            response_time_ms = int((time.perf_counter() - start_time) * 1000)
            response_data = response.json()
            
            self._log_usage(
                user=user,
                request_type="content_generation",
                usage_data=response_data.get("usage", {}),
                response_time_ms=response_time_ms
            )

            # The actual content is a JSON string, so we parse it.
            try:
                # Note: The AI is expected to return a JSON string as the message content
                content_payload = json.loads(response_data["choices"][0]["message"]["content"])
                return content_payload
            except (json.JSONDecodeError, KeyError, IndexError):
                raise AIAPIError("Failed to parse valid content from AI response.")

        except requests.exceptions.Timeout:
            raise AIConnectionError(f"Request timed out after {REQUEST_TIMEOUT} seconds.")
        except requests.exceptions.RequestException as e:
            raise AIConnectionError(f"API request failed: {e}")
        except Exception as e:
            # Catch-all for other unexpected errors
            raise AIClientError(f"An unexpected error occurred: {e}")

    def _log_usage(self, user: Optional[settings.AUTH_USER_MODEL], request_type: str, usage_data: Dict[str, int], response_time_ms: int):
        """
        Logs the AI API usage to the database.
        """
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        
        cost = self._calculate_cost(prompt_tokens, completion_tokens)

        AIUsageLog.objects.create(
            user=user,
            request_type=request_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=usage_data.get("total_tokens", 0),
            cost=cost,
            response_time_ms=response_time_ms
        )

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> Decimal:
        """
        Calculates the cost based on DeepSeek's pricing model using Decimal for precision.
        """
        # Set precision for Decimal calculations
        getcontext().prec = 10

        # Prices per 1,000 tokens, as Decimal objects
        prompt_cost_per_1k = Decimal('0.0014')
        completion_cost_per_1k = Decimal('0.0028')
        
        # Use Decimal for all calculations to avoid floating point inaccuracies
        prompt_cost = (Decimal(prompt_tokens) / Decimal(1000)) * prompt_cost_per_1k
        completion_cost = (Decimal(completion_tokens) / Decimal(1000)) * completion_cost_per_1k
        
        return prompt_cost + completion_cost 