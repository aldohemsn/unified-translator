import os
import time
import random
import logging
from typing import Optional, Dict, Any, Union
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the LLM Client with configuration.
        """
        self.config = config.get('llm', {})
        self.api_key_env = self.config.get('api_key_env_var', 'GEMINI_API_KEY')
        self.api_key = os.getenv(self.api_key_env)
        
        if not self.api_key:
            raise ValueError(f"API Key not found in environment variable: {self.api_key_env}")
            
        self.client = genai.Client(api_key=self.api_key)
        self.default_model = self.config.get('default_model', 'gemini-2.5-flash')
        self.max_retries = self.config.get('max_retries', 3)
        self.timeout = self.config.get('timeout', 60)

    def generate(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None, 
        model: Optional[str] = None,
        temperature: float = 0.5,
        response_schema: Optional[Any] = None,
        response_mime_type: Optional[str] = None
    ) -> str:
        """
        Generate content from Gemini with exponential backoff retry logic.
        """
        model_name = model or self.default_model
        
        config_args = {
            "temperature": temperature,
        }
        
        if system_instruction:
            config_args["system_instruction"] = system_instruction
            
        if response_schema:
            config_args["response_schema"] = response_schema
        
        if response_mime_type:
            config_args["response_mime_type"] = response_mime_type

        generate_config = types.GenerateContentConfig(**config_args)

        attempts = 0
        while attempts < self.max_retries:
            try:
                # Add simple timeout handling via basic socket timeout if supported, 
                # but google-genai client handles it largely internally.
                # We focus on retry logic here.
                
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=generate_config
                )
                
                if not response.text:
                    logger.warning("Empty response received from LLM.")
                    raise ValueError("Empty response from LLM")
                    
                return response.text

            except Exception as e:
                attempts += 1
                logger.warning(f"LLM Generation failed (Attempt {attempts}/{self.max_retries}): {e}")
                
                if attempts >= self.max_retries:
                    logger.error("Max retries reached. Raising exception.")
                    raise e
                
                self._wait_with_backoff(attempts)
                
        return ""

    def _wait_with_backoff(self, attempt: int):
        """
        Exponential backoff with jitter: 2s, 4s, 8s... + random jitter
        """
        base_delay = 2 * (2 ** (attempt - 1))
        jitter = random.uniform(0, 1)
        sleep_time = min(base_delay + jitter, 60) # Cap at 60s
        logger.info(f"Waiting {sleep_time:.2f}s before retry...")
        time.sleep(sleep_time)

    def test_connection(self) -> bool:
        """
        Simple connectivity test.
        """
        try:
            val = self.generate("Say 'OK'", model="gemini-2.5-flash")
            return "OK" in val or len(val) > 0
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
