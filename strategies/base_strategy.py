from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging
from ..core.llm_client import LLMClient
from ..core.context_window import ContextWindowBuilder

logger = logging.getLogger(__name__)

class BaseStrategy(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = "BaseStrategy"

    @abstractmethod
    def setup(self, input_file_path: str, context_files: Dict[str, str] = None) -> None:
        """
        Perform any initialization analysis, e.g., generating persona, 
        loading glossary, analyzing source text.
        """
        pass

    @abstractmethod
    def process_batch(
        self, 
        llm_client: LLMClient, 
        batch_rows: List[Dict[str, str]], 
        history_rows: List[Dict[str, str]],
        window_builder: ContextWindowBuilder
    ) -> List[Dict[str, str]]:
        """
        Process a batch of rows. 
        Must return a list of dicts with at least 'ID', 'Source', 'Target'.
        """
        pass
