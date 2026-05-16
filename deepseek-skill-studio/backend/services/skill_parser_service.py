"""
Skill Parser Service — parses SKILL.md files to extract structured metadata.

Provider detection heuristics:
  - OpenClaw: specific section headers (## OpenClaw, <!-- openclaw -->),
    or a source filename path containing "openclaw"
  - Claude: references to claude.ai, Anthropic models, or the word "claude"
  - ChatGPT: references to openai.com, gpt-4, chatgpt
  - AgentSkills: agentskills.io marker
  - local: default / unrecognised
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("agentstudio.skill_parser")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SkillMeta:
    name: str
    description: str
    rules: List[str]
    provider: str  # "local" | "openclaw" | "chatgpt" | "claude" | "agentskills"
    raw_content: str


# ---------------------------------------------------------------------------
# Provider detection helpers
# ---------------------------------------------------------------------------

_OPENCLAW_MARKERS = re.compile(
    r"<!--\s*openclaw\s*-->|##\s*OpenClaw|<!-- openclaw-skill -->|^source:\s*openclaw",
    re.IGNORECASE | re.MULTILINE,
)

_CLAUDE_MARKERS = re.compile(
    r"claude\.ai|anthropic|claude-sonnet|claude-haiku|claude-opus|claude-3",
    re.IGNORECASE,
)

_CHATGPT_MARKERS = re.compile(
    r"openai\.com|gpt-4|gpt-3\.5|chatgpt|chat\.openai",
    re.IGNORECASE,
)

_AGENTSKILLS_MARKERS = re.compile(
    r"agentskills\.io|<!-- agentskills -->",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SkillParserService:
    """
    Parses the textual content of a SKILL.md file into a SkillMeta.

    Extraction strategy
    -------------------
    name:
        First ``# Heading`` found; falls back to ``filename`` stem or "unnamed".
    description:
        First non-empty paragraph that follows the name heading, before any
        ``##`` sub-heading.
    rules:
        Bullet items (``-``, ``*``, ``+``) inside the first ``## Rules``
        (or ``## Guidelines`` / ``## Instructions``) section.
    provider:
        Detected by scanning the full content for known markers.
    """

    def parse(self, content: str, filename: str = "") -> SkillMeta:
        name = self._extract_name(content, filename)
        description = self._extract_description(content)
        rules = self._extract_rules(content)
        provider = self.detect_source(content, filename)

        return SkillMeta(
            name=name,
            description=description,
            rules=rules,
            provider=provider,
            raw_content=content,
        )

    # ── Extraction helpers ─────────────────────────────────────────────────

    @staticmethod
    def _extract_name(content: str, filename: str = "") -> str:
        """Return the first ``# Heading`` in *content*, or derive from filename."""
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        if filename:
            stem = re.sub(r"[_\-]+", " ", re.sub(r"\.md$", "", filename, flags=re.IGNORECASE))
            stem = re.sub(r".*/", "", stem)  # basename
            return stem.strip().title() or "Unnamed Skill"
        return "Unnamed Skill"

    @staticmethod
    def _extract_description(content: str) -> str:
        """
        Return the first paragraph of text after the ``# Heading`` line
        and before any ``##`` sub-heading.
        """
        lines = content.splitlines()
        in_header_section = False
        paragraph_lines: List[str] = []
        found_top_heading = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("# ") and not found_top_heading:
                found_top_heading = True
                in_header_section = True
                continue

            if not found_top_heading:
                continue

            if stripped.startswith("## ") or stripped.startswith("---"):
                break

            if stripped:
                paragraph_lines.append(stripped)
            elif paragraph_lines:
                # Blank line ends the first paragraph
                break

        return " ".join(paragraph_lines).strip()

    @staticmethod
    def _extract_rules(content: str) -> List[str]:
        """
        Return bullet items from the first section whose heading matches
        'Rules', 'Guidelines', or 'Instructions'.
        """
        _rule_heading = re.compile(
            r"^##\s+(Rules|Guidelines|Instructions)\b",
            re.IGNORECASE,
        )
        _bullet = re.compile(r"^[\-\*\+]\s+(.+)")
        _any_heading = re.compile(r"^#{1,6}\s+")

        lines = content.splitlines()
        in_section = False
        rules: List[str] = []

        for line in lines:
            stripped = line.strip()
            if _rule_heading.match(stripped):
                in_section = True
                continue
            if in_section:
                if _any_heading.match(stripped) and stripped.startswith("##"):
                    break  # Next section
                m = _bullet.match(stripped)
                if m:
                    rules.append(m.group(1).strip())

        return rules

    # ── Provider detection ─────────────────────────────────────────────────

    def detect_source(self, content: str, filename: str = "") -> str:
        """
        Detect the originating platform for a skill.

        Priority order:
        1. OpenClaw marker in content or "openclaw" in filename path
        2. AgentSkills marker
        3. Claude marker
        4. ChatGPT marker
        5. "local"
        """
        lower_fname = filename.lower()

        if _OPENCLAW_MARKERS.search(content) or "openclaw" in lower_fname:
            return "openclaw"

        if _AGENTSKILLS_MARKERS.search(content):
            return "agentskills"

        if _CLAUDE_MARKERS.search(content):
            return "claude"

        if _CHATGPT_MARKERS.search(content):
            return "chatgpt"

        return "local"
