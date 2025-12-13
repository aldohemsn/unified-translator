"""
Base Strategy Abstract Class
Provides configuration interface and common utilities for all translation strategies.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BaseStrategy(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = "BaseStrategy"
        self._strategy_config: Dict[str, Any] = {}
    
    def _get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """
        Load strategy-specific configuration from the global config.
        """
        return self.config.get('strategies', {}).get(strategy_name, {})
    
    # =========================================================================
    # Configuration Accessors (with defaults)
    # =========================================================================
    
    def get_context_window(self) -> Dict[str, int]:
        """Get sliding window size (before, after)."""
        default = {'before': 3, 'after': 2}
        return self._strategy_config.get('context_window', default)
    
    def get_batch_size(self) -> int:
        """Get processing batch size."""
        strategy_batch = self._strategy_config.get('batch_size')
        if strategy_batch:
            return strategy_batch
        return self.config.get('processing', {}).get('batch_size', 15)
    
    def should_inject_full_context(self) -> bool:
        """Whether to inject full document context into prompts."""
        return self._strategy_config.get('inject_full_context', False)
    
    def get_full_context_max_chars(self) -> int:
        """Maximum characters for full context injection."""
        return self._strategy_config.get('full_context_max_chars', 2000)
    
    def should_enable_cross_row_merging(self) -> bool:
        """Whether to allow cross-row sentence merging."""
        return self._strategy_config.get('cross_row_merging', False)
    
    def get_glossary_enforcement_level(self) -> str:
        """Get glossary enforcement level: strict, moderate, none."""
        return self._strategy_config.get('glossary_enforcement', 'moderate')
    
    def should_enable_qa_check(self) -> bool:
        """Whether to perform post-processing QA check."""
        return self._strategy_config.get('enable_qa_check', False)
    
    # =========================================================================
    # CIL-specific (Legal)
    # =========================================================================
    
    def should_enable_layman_logic(self) -> bool:
        """Whether to generate Layman's Logic (Feynman explanation)."""
        cil_config = self._strategy_config.get('cil', {})
        return cil_config.get('enable_logic', True)
    
    def should_enable_insight(self) -> bool:
        """Whether to generate domain insight."""
        cil_config = self._strategy_config.get('cil', {})
        return cil_config.get('enable_insight', True)
    
    # =========================================================================
    # Video-specific
    # =========================================================================
    
    def should_enable_transcription_audit(self) -> bool:
        """Whether to perform transcription error audit."""
        return self._strategy_config.get('enable_transcription_audit', False)
    
    def get_blacklist_terms(self) -> List[str]:
        """Get translationese blacklist terms."""
        return self._strategy_config.get('blacklist_terms', [])
    
    # =========================================================================
    # Abstract Methods (must be implemented by subclasses)
    # =========================================================================
    
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
        llm_client: 'LLMClient', 
        batch_rows: List[Dict[str, str]], 
        history_rows: List[Dict[str, str]],
        window_builder: 'ContextWindowBuilder'
    ) -> List[Dict[str, str]]:
        """
        Process a batch of rows. 
        Must return a list of dicts with at least 'ID', 'Source', 'Target'.
        """
        pass
