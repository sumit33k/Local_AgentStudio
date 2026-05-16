"""Skill CRUD endpoints."""
import re
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

APP_DIR = Path(__file__).parent.parent
SKILLS_DIR = APP_DIR / "skills"


def list_skill_names() -> List[str]:
    if not SKILLS_DIR.exists():
        return []
    return sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").exists())


def read_skill(name: str) -> str:
    path = SKILLS_DIR / name / "SKILL.md"
    if not path.exists():
        raise HTTPException(404, f"Skill not found: {name}")
    return path.read_text(encoding="utf-8")


def _safe_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", name.lower()).strip("_")
    if not slug:
        raise HTTPException(400, "Invalid skill name")
    return slug


def _build_skill_md(name: str, description: str, rules: List[str]) -> str:
    lines = [f"# {name.replace('_', ' ').title()} Skill", "", description, "", "## Rules", ""]
    for rule in rules:
        lines.append(f"- {rule}")
    return "\n".join(lines)


# ── Pydantic models ─────────────────────────────────────────────────────

class SkillCreate(BaseModel):
    name: str
    description: str
    rules: List[str]


class SkillUpdate(BaseModel):
    description: Optional[str] = None
    rules: Optional[List[str]] = None


# ── Endpoints ───────────────────────────────────────────────────────────

@router.get("/skills")
def list_skills():
    return {"skills": list_skill_names()}


@router.get("/skills/{name}")
def get_skill(name: str):
    safe = _safe_name(name)
    content = read_skill(safe)
    return {"name": safe, "content": content}


@router.post("/skills")
def create_skill(body: SkillCreate):
    safe = _safe_name(body.name)
    skill_dir = SKILLS_DIR / safe
    if skill_dir.exists():
        raise HTTPException(409, f"Skill '{safe}' already exists")
    skill_dir.mkdir(parents=True)
    content = _build_skill_md(safe, body.description, body.rules)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return {"name": safe, "content": content}


@router.put("/skills/{name}")
def update_skill(name: str, body: SkillUpdate):
    name = _safe_name(name)
    path = SKILLS_DIR / name / "SKILL.md"
    if not path.exists():
        raise HTTPException(404, f"Skill not found: {name}")
    existing = path.read_text(encoding="utf-8")
    # Parse existing description and rules if not provided
    lines = existing.splitlines()
    # Extract description (line after title + blank)
    desc = body.description
    if desc is None:
        # Pull from existing: first non-header, non-blank line after title
        for i, line in enumerate(lines):
            if i > 0 and line and not line.startswith("#"):
                desc = line
                break
        desc = desc or ""
    rules = body.rules
    if rules is None:
        rules = [
            line[2:].strip()
            for line in lines
            if line.startswith("- ")
        ]
    content = _build_skill_md(name, desc, rules)
    path.write_text(content, encoding="utf-8")
    return {"name": name, "content": content}


@router.delete("/skills/{name}")
def delete_skill(name: str):
    import shutil
    name = _safe_name(name)
    skill_dir = SKILLS_DIR / name
    if not skill_dir.exists():
        raise HTTPException(404, f"Skill not found: {name}")
    shutil.rmtree(skill_dir)
    return {"deleted": name}
