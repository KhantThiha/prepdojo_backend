import json
from pathlib import Path
from typing import List, Dict
from app.core.config import settings

CURRENT_DIR = Path(__file__).parent
FORMAT_PATH = CURRENT_DIR / "jlpt_official_format.json"

def load_official_format() -> Dict:
    with open(FORMAT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_exam_tasks(level: str, mock: bool = False) -> List[Dict]:
    """
    Parses the official JLPT format JSON and generates a task queue.
    
    Args:
        level (str): JLPT level (e.g., "N3").
        mock (bool): If True, generates only 1 question per valid type.
                     If False, generates the full official count.
    """
    format_data = load_official_format()
    task_queue = []
    
    section_order = ["Vocabulary", "Grammar", "Reading", "Listening"]

    def sanitize_key(key: str) -> str:
        return key.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")

    for section in section_order:
        if section not in format_data:
            continue
            
        sub_types = format_data[section]
        
        for sub_type_name, levels in sub_types.items():
            # Get count for the requested level
            count = levels.get(level)
            
            # REQUIREMENT: Skip if count is null or 0
            # This ensures N3 doesn't get "Word formation" (which is null)
            if not count:
                continue
                
            # REQUIREMENT: If Mock Mode is active, force count to 1
            if mock:
                count = 1
                
            # To avoid overwhelming the LLM and hitting tool generation limits (especially with large counts),
            # split large counts into smaller batches of max 5.
            max_batch_size = 5
            
            while count > 0:
                batch_count = min(count, max_batch_size)
                # Generate tasks with a count property instead of multiple items
                task = {
                    "section": section,
                    "sub_type": sub_type_name,
                    "code": sanitize_key(sub_type_name),
                    "level": level,
                    "count": batch_count
                }
                task_queue.append(task)
                count -= batch_count
                
    return task_queue