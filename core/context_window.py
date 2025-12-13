from typing import List, Dict, Any

class ContextWindowBuilder:
    def __init__(self, raw_data: List[Dict[str, str]], window_before: int = 3, window_after: int = 2):
        self.data = raw_data
        self.before = window_before
        self.after = window_after
    
    def build(self, current_index: int) -> str:
        """
        Build a context window around the current row for LLM prompting.
        Returns a formatted string containing:
        - Preceding N rows (Source + Target)
        - Current row (marked for review)
        - Following M rows (Source only)
        """
        start = max(0, current_index - self.before)
        end = min(len(self.data), current_index + self.after + 1)
        
        context_parts = []
        
        for i in range(start, end):
            row = self.data[i]
            row_id = row.get('ID', str(i))
            source = (row.get('Source') or '')[:100] # Truncate for brevity in prompt
            target = (row.get('Target') or '')[:100]
            
            if i == current_index:
                # Current row - marked for review
                context_parts.append(f">>> [Segment {row_id} - TARGET]:")
                context_parts.append(f"    Source: {row.get('Source', '')}")
                context_parts.append(f"    Target (Draft): {row.get('Target', '')}")
            elif i < current_index:
                # Preceding rows - show both Source and Target
                context_parts.append(f"[Segment {row_id}]: {source}...")
                context_parts.append(f"    -> {target}...")
            else:
                # Following rows - show Source only
                context_parts.append(f"[Segment {row_id}]: {source}...")
        
        return "\n".join(context_parts)
    
    def get_window_stats(self, current_index: int) -> Dict[str, int]:
        """Return stats about the window for debugging."""
        start = max(0, current_index - self.before)
        end = min(len(self.data), current_index + self.after + 1)
        return {
            "current": current_index,
            "window_start": start,
            "window_end": end - 1,
            "preceding_count": current_index - start,
            "following_count": end - 1 - current_index
        }
