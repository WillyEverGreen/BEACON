# tag.py
import re

WCAG_SC_RE = re.compile(r'\b(\d\.\d+\.\d+)\b')

SEVERITY_MAP = {
    "A":   ["level a","(level a)","level-a","conformance level a"],
    "AA":  ["level aa","(level aa)","level double-a","level-aa"],
    "AAA": ["level aaa","(level aaa)","level triple-a","level-aaa"],
}

ISSUE_TYPES = {
    "images":      ["alt text","non-text content","1.1.1","decorative image","image of text"],
    "keyboard":    ["keyboard","focus","tab order","keyboard trap","tabindex","2.1","focus visible","2.4.7","2.4.11","2.4.12"],
    "color":       ["contrast","color alone","1.4.3","1.4.11","1.4.1","color blindness","4.5:1","3:1","7:1"],
    "structure":   ["heading","landmark","semantic","1.3.1","h1","h2","skip navigation","2.4.1","dom order","reading order"],
    "forms":       ["label","input","error","3.3","fieldset","legend","autocomplete","aria-describedby","3.3.1","3.3.2","3.3.7","3.3.8","3.3.9"],
    "timing":      ["timeout","pause","2.2","time limit","session"],
    "motion":      ["animation","flashing","2.3","prefers-reduced-motion","seizure","three flashes"],
    "cognitive":   ["coga","cognitive","plain language","memory","reading level","unusual terms","abbreviations","3.1.3","3.1.4","3.1.5","3.1.6"],
    "aria":        ["aria-","role=","aria-label","aria-labelledby","aria-live","aria-expanded","aria-selected","aria-hidden","aria-checked"],
    "media":       ["captions","audio description","transcript","1.2","sign language","media alternative"],
    "links":       ["link text","new window","new tab","target size","24px","44px","2.5.8","2.5.5","click here"],
    "language":    ["lang attribute","language of page","3.1.1","3.1.2","foreign phrase"],
    "responsive":  ["reflow","320px","zoom","resize","1.4.10","1.4.4","viewport","horizontal scroll"],
    "appearance":  ["prefers-color-scheme","prefers-contrast","prefers-reduced-transparency","custom fonts","dyslexia"],
    "tables":      ["table","thead","tbody","th scope","caption","tabular data"],
    "navigation":  ["consistent help","3.2.6","redundant entry","3.3.7","dragging","2.5.7"],
    "auth":        ["accessible authentication","3.3.8","3.3.9","cognitive function test","captcha"],
    "focus":       ["focus not obscured","2.4.11","2.4.12","focus appearance","2.4.13","focus indicator"],
    "target":      ["target size","2.5.8","2.5.7","dragging movements","minimum 24px"],
}

USER_IMPACT = {
    "blind":          ["screen reader","alt text","1.1","aria","role=","non-text"],
    "low_vision":     ["contrast","resize","zoom","1.4.3","1.4.4","1.4.10","reflow"],
    "motor":          ["keyboard","pointer","timeout","2.1","2.2","target size","tabindex","dragging","2.5.7","2.5.8"],
    "deaf":           ["captions","transcript","sign language","1.2","audio"],
    "cognitive":      ["coga","plain language","reading level","memory","abbreviation","unusual terms","redundant entry","3.3.7","3.3.8","3.3.9","accessible authentication"],
    "photosensitive": ["flashing","animation","2.3","seizure","three flashes"],
    "dyslexia":       ["custom fonts","dyslexia","reading","spacing","1.4.12"],
}

def tag_chunk(chunk: dict) -> dict:
    text = chunk["text"].lower()
    raw  = chunk["text"]

    chunk["wcag_sc"]     = list(set(WCAG_SC_RE.findall(raw)))
    chunk["issue_types"] = [k for k, kws in ISSUE_TYPES.items() if any(kw in text for kw in kws)]
    chunk["issue_type"]  = chunk["issue_types"][0] if chunk["issue_types"] else "general"
    chunk["user_impact"] = [u for u, kws in USER_IMPACT.items() if any(kw in text for kw in kws)] or ["general"]
    chunk["severity"]    = "unknown"
    for lvl, kws in SEVERITY_MAP.items():
        if any(kw in text for kw in kws):
            chunk["severity"] = lvl
            break

    heading = re.search(r'^#{1,4}\s+(.+)$', raw, re.MULTILINE)
    chunk["topic"] = heading.group(1).strip() if heading else ""
    chunk["token_count"] = len(raw.split())

    return chunk
