# axe_parser.py
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def parse_axe_rules(rules_path="../axe-core/lib/rules"):
    chunks = []
    path = Path(rules_path)
    if not path.exists():
        logger.info(f"Axe rules path {rules_path} not found. Skipping axe parser.")
        return chunks
        
    for f in path.glob("*.json"):
        rule = json.loads(f.read_text())
        text = (
            f"Rule: {rule['id']}\n"
            f"Description: {rule.get('description','')}\n"
            f"Help: {rule.get('help','')}\n"
            f"Tags: {', '.join(rule.get('tags',[]))}\n"
            f"Impact: {rule.get('impact','')}\n"
            f"Help URL: {rule.get('helpUrl','')}"
        )
        chunks.append({
            "text": text, "silo": "axe",
            "rule_id": rule["id"],
            "url": rule.get("helpUrl", "")
        })
    return chunks
