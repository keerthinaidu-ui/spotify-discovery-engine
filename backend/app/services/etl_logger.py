import logging
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

class ETLTruncationTracker:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(ETLTruncationTracker, cls).__new__(cls, *args, **kwargs)
                cls._instance.reset()
            return cls._instance

    def reset(self):
        # key: (table, column) -> list of dicts with row_id, original_len, truncated_len
        self._truncations = defaultdict(list)

    def track_truncation(self, table: str, column: str, row_id: str, original_len: int, truncated_len: int):
        self._truncations[(table, column)].append({
            "row_id": row_id,
            "original_len": original_len,
            "truncated_len": truncated_len
        })
        logger.warning(
            f"ETL TRUNCATION: Table '{table}', Column '{column}', Row ID '{row_id}' value "
            f"truncated from {original_len} to {truncated_len} characters."
        )

    def get_report(self) -> str:
        if not self._truncations:
            return "No fields were truncated during this ETL run."

        lines = ["=== ETL TRUNCATION REPORT ==="]
        lines.append(f"{'Table':<25} | {'Column':<25} | {'Rows Truncated':<15}")
        lines.append("-" * 73)
        
        for (table, col), occurrences in sorted(self._truncations.items()):
            lines.append(f"{table:<25} | {col:<25} | {len(occurrences):<15}")
            
        lines.append("\nDetailed Truncation Log:")
        for (table, col), occurrences in sorted(self._truncations.items()):
            lines.append(f"\nTable: {table}, Column: {col}")
            for occ in occurrences[:10]:  # Limit details to first 10 occurrences
                lines.append(
                    f"  - Row ID: {occ['row_id']}, Original Length: {occ['original_len']}, "
                    f"Truncated Length: {occ['truncated_len']}"
                )
            if len(occurrences) > 10:
                lines.append(f"  - ... and {len(occurrences) - 10} more occurrences.")
                
        return "\n".join(lines)

    @property
    def total_truncations(self) -> int:
        return sum(len(x) for x in self._truncations.values())

# Global singleton instance
tracker = ETLTruncationTracker()
