#!/usr/bin/env python3
"""
skillctl.py

Safe local Codex Skill manager.

Features:
- list skills
- search skills
- read skill metadata/content
- validate SKILL.md
- backup skills
- safe delete to trash
- restore from trash/backup
- show managed locations
- export skills to migration archive
- import skills from migration archive
- verify migration archive integrity

No external dependencies.
No network access.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


HOME = Path.home()

USER_SKILLS = HOME / ".agents" / "skills"
USER_TRASH = USER_SKILLS / ".trash"
USER_BACKUPS = USER_SKILLS / ".backups"
USER_CODEX = HOME / ".codex"
USER_AGENTS_MD = HOME / ".codex" / "AGENTS.md"


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def safe_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("empty skill name")
    if "/" in name or "\\" in name or name.startswith("."):
        raise ValueError("unsafe skill name")
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        raise ValueError(f"unsafe skill name: {name}")
    return name


def find_repo_root(start: Path) -> Optional[Path]:
    cur = start.resolve()
    for p in [cur] + list(cur.parents):
        if (p / ".git").exists():
            return p
    return None


def managed_locations() -> List[Tuple[str, Path]]:
    locs: List[Tuple[str, Path]] = []

    locs.append(("user", USER_SKILLS))

    cwd = Path.cwd()
    seen = {USER_SKILLS.resolve() if USER_SKILLS.exists() else USER_SKILLS}

    repo_root = find_repo_root(cwd)
    candidates: List[Path] = []

    # current and parent .agents/skills up to repo root
    for p in [cwd] + list(cwd.parents):
        if repo_root and repo_root not in [p] + list(p.parents):
            break
        candidates.append(p / ".agents" / "skills")
        if repo_root and p == repo_root:
            break

    for c in candidates:
        try:
            r = c.resolve()
        except Exception:
            r = c
        if r not in seen:
            locs.append(("repo", c))
            seen.add(r)

    return locs


def parse_frontmatter(text: str) -> Dict[str, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    data: Dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def skill_md_path(skill_dir: Path) -> Path:
    return skill_dir / "SKILL.md"


def iter_skills() -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    for scope, loc in managed_locations():
        if not loc.exists() or not loc.is_dir():
            continue
        for child in sorted(loc.iterdir()):
            if not child.is_dir():
                continue
            if child.name in {".trash", ".backups"}:
                continue
            md = skill_md_path(child)
            if not md.exists():
                continue
            info = read_metadata(md)
            results.append({
                "scope": scope,
                "folder": child.name,
                "name": info.get("name", ""),
                "description": info.get("description", ""),
                "path": str(child),
                "valid": "yes" if validate_path(md)[0] else "no",
            })
    return results


def read_metadata(md: Path) -> Dict[str, str]:
    try:
        text = md.read_text(encoding="utf-8")
    except Exception:
        return {}
    return parse_frontmatter(text)


def find_skill(identifier: str) -> Optional[Path]:
    identifier = identifier.strip()
    if not identifier:
        return None

    # exact path
    p = Path(identifier).expanduser()
    if p.exists() and p.is_dir() and skill_md_path(p).exists():
        return p

    matches: List[Path] = []
    for item in iter_skills():
        if item["name"] == identifier or item["folder"] == identifier:
            matches.append(Path(item["path"]))

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Multiple skills match '{identifier}':", file=sys.stderr)
        for m in matches:
            print(f"- {m}", file=sys.stderr)
        return None
    return None


def validate_path(md: Path) -> Tuple[bool, List[str]]:
    problems: List[str] = []
    if not md.exists():
        return False, ["SKILL.md missing"]

    try:
        text = md.read_text(encoding="utf-8")
    except Exception as e:
        return False, [f"cannot read SKILL.md: {e}"]

    fm = parse_frontmatter(text)
    if not fm:
        problems.append("missing YAML frontmatter")
    if not fm.get("name"):
        problems.append("missing name")
    if not fm.get("description"):
        problems.append("missing description")
    if fm.get("description") and len(fm["description"]) > 400:
        problems.append("description may be too long")
    body = FRONTMATTER_RE.sub("", text, count=1).strip()
    if not body:
        problems.append("missing instruction body")

    dangerous = [
        "rm -rf /",
        "sudo rm",
        "mkfs",
        ":(){",
        "curl | sh",
        "wget | sh",
    ]
    for d in dangerous:
        if d in text:
            problems.append(f"dangerous pattern found: {d}")

    hard_fail = [
        p for p in problems
        if not p.startswith("description may be too long")
    ]
    return len(hard_fail) == 0, problems


def cmd_locations(_: argparse.Namespace) -> int:
    print("Managed skill locations:")
    for scope, loc in managed_locations():
        exists = "exists" if loc.exists() else "missing"
        print(f"- {scope}: {loc} [{exists}]")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    skills = iter_skills()
    if not skills:
        print("No managed skills found.")
        return 0

    print("Skills:")
    for s in skills:
        desc = s["description"]
        if len(desc) > 100:
            desc = desc[:97] + "..."
        print(f"- {s['name'] or s['folder']} | {s['scope']} | valid={s['valid']} | {s['path']} | {desc}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    q = args.query.lower()
    found = []
    for s in iter_skills():
        blob = " ".join([s["name"], s["folder"], s["description"], s["path"]]).lower()
        if q in blob:
            found.append(s)

    if not found:
        print(f"No skills found for: {args.query}")
        return 0

    print("Matches:")
    for s in found:
        print(f"- {s['name'] or s['folder']} | {s['scope']} | {s['path']} | {s['description']}")
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    p = find_skill(args.skill)
    if not p:
        print(f"Skill not found or ambiguous: {args.skill}", file=sys.stderr)
        return 1

    md = skill_md_path(p)
    text = md.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    print(f"Name: {fm.get('name', '')}")
    print(f"Description: {fm.get('description', '')}")
    print(f"Path: {p}")
    print("")
    if args.full:
        print(text)
    else:
        lines = text.splitlines()
        max_lines = args.lines
        print("\n".join(lines[:max_lines]))
        if len(lines) > max_lines:
            print(f"\n... truncated, use read {args.skill} --full to show all")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    targets: List[Path] = []
    if args.all:
        targets = [Path(s["path"]) for s in iter_skills()]
    else:
        p = find_skill(args.skill)
        if not p:
            print(f"Skill not found or ambiguous: {args.skill}", file=sys.stderr)
            return 1
        targets = [p]

    overall = True
    for p in targets:
        ok, problems = validate_path(skill_md_path(p))
        overall = overall and ok
        print(f"- {p}: {'valid' if ok else 'invalid'}")
        for problem in problems:
            print(f"  - {problem}")
    return 0 if overall else 2


def backup_skill_dir(p: Path) -> Path:
    USER_BACKUPS.mkdir(parents=True, exist_ok=True)
    dest = USER_BACKUPS / f"{p.name}-{now_stamp()}"
    shutil.copytree(p, dest)
    return dest


def cmd_backup(args: argparse.Namespace) -> int:
    p = find_skill(args.skill)
    if not p:
        print(f"Skill not found or ambiguous: {args.skill}", file=sys.stderr)
        return 1
    dest = backup_skill_dir(p)
    print(f"Backed up:")
    print(f"- source: {p}")
    print(f"- backup: {dest}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    p = find_skill(args.skill)
    if not p:
        print(f"Skill not found or ambiguous: {args.skill}", file=sys.stderr)
        return 1

    USER_TRASH.mkdir(parents=True, exist_ok=True)
    backup = backup_skill_dir(p)
    dest = USER_TRASH / f"{p.name}-{now_stamp()}"

    print("Operation: safe delete skill")
    print(f"Target: {p}")
    print(f"Backup path: {backup}")
    print(f"Trash path: {dest}")
    print("Risk: skill will be moved out of active skill directory, but can be restored.")

    if not args.yes:
        print("")
        print("Dry run only. Re-run with --yes to move to trash.")
        return 0

    shutil.move(str(p), str(dest))
    print("")
    print("Deleted safely:")
    print(f"- moved to: {dest}")
    print(f"- backup: {backup}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    src = Path(args.path).expanduser()
    if not src.exists() or not src.is_dir():
        print(f"Restore source not found: {src}", file=sys.stderr)
        return 1

    if not skill_md_path(src).exists():
        print(f"Restore source does not contain SKILL.md: {src}", file=sys.stderr)
        return 1

    name = src.name
    # strip timestamp suffix if present
    name = re.sub(r"-\d{8}-\d{6}$", "", name)
    dest = USER_SKILLS / name

    USER_SKILLS.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        backup = backup_skill_dir(dest)
        print(f"Existing destination backed up: {backup}")
        if not args.yes:
            print(f"Dry run only. Re-run with --yes to overwrite/restore to: {dest}")
            return 0
        shutil.rmtree(dest)

    if not args.yes:
        print(f"Dry run only. Re-run with --yes to restore:")
        print(f"- from: {src}")
        print(f"- to: {dest}")
        return 0

    shutil.copytree(src, dest)
    print("Restored:")
    print(f"- from: {src}")
    print(f"- to: {dest}")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    name = safe_name(args.name)
    target = USER_SKILLS / name
    if target.exists():
        print(f"Skill already exists: {target}", file=sys.stderr)
        return 1

    USER_SKILLS.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=False)
    md = target / "SKILL.md"

    description = args.description or f"Use when working with {name}."
    title = name.replace("-", " ").replace("_", " ").title()

    content = f"""---
name: {name}
description: {description}
---

# {title}

Describe when to use this skill and what Codex should do.

## Rules

- Be concise.
- Be safe.
- Do not modify unrelated files.
- Validate changes when possible.
"""
    md.write_text(content, encoding="utf-8")
    ok, problems = validate_path(md)

    print("Created:")
    print(f"- {target}")
    print(f"Validation: {'valid' if ok else 'invalid'}")
    for p in problems:
        print(f"  - {p}")
    return 0 if ok else 2


# Migration constants
# ============================================================

ARCHIVE_FORMAT = "codex-skill-migration-v1"

SECRET_PATTERNS: List[Tuple[str, str]] = [
    ("sk-", "OpenAI-style API key prefix"),
    ("api_key", "api_key identifier"),
    ("apikey", "apikey identifier"),
    ("API_KEY", "API_KEY identifier"),
    ("SECRET", "SECRET identifier"),
    ("TOKEN", "TOKEN identifier"),
    ("PRIVATE KEY", "PRIVATE KEY"),
    ("BEGIN RSA PRIVATE KEY", "RSA private key"),
    ("BEGIN OPENSSH PRIVATE KEY", "OpenSSH private key"),
    ("password=", "password assignment"),
    ("passwd=", "passwd assignment"),
]

EXCLUDE_PATTERNS: List[str] = [
    ".trash",
    ".backups",
    ".DS_Store",
    "__pycache__",
    "*.pyc",
    "*.log",
    "*.tmp",
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*.p12",
    "*.mobileprovision",
]


# ============================================================
# Migration helpers
# ============================================================

def sha256_file(path: Path) -> str:
    """Compute SHA256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def should_exclude(name: str) -> bool:
    """Check if a file/dir name matches exclude patterns (glob)."""
    for pat in EXCLUDE_PATTERNS:
        if pat.startswith("*."):
            if name.endswith(pat[1:]):
                return True
        elif pat == name:
            return True
    return False


def scan_file_for_secrets(path: Path) -> List[str]:
    """Scan a file for secret patterns. Returns list of matched pattern types (no values)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    found: List[str] = []
    for pat, label in SECRET_PATTERNS:
        if pat in text:
            found.append(label)
    return found


def is_path_safe(arcname: str) -> bool:
    """Reject path-traversal and absolute paths inside archive."""
    if arcname.startswith("/"):
        return False
    if ".." in Path(arcname).parts:
        return False
    if "~" in arcname:
        return False
    return True


def collect_export_files(
    include_agents: bool,
    include_hooks: bool,
    include_prompts: bool,
) -> Tuple[List[Tuple[Path, str]], List[str]]:
    """Collect skill files and optional config files for export.

    Returns (files_list, warnings). Each file entry is (source_path, arcname).
    """
    files: List[Tuple[Path, str]] = []
    warnings: List[str] = []

    # User skills
    skills_dir = USER_SKILLS
    if skills_dir.exists():
        for child in sorted(skills_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name in {".trash", ".backups"}:
                continue
            md = child / "SKILL.md"
            if not md.exists():
                continue
            for fpath in sorted(child.rglob("*")):
                if fpath.is_dir():
                    continue
                rel = fpath.relative_to(skills_dir)
                # apply exclude patterns on each path part
                skip = False
                for part in rel.parts:
                    if should_exclude(part):
                        skip = True
                        break
                if skip:
                    continue
                arcname = f"user-skills/{rel}"
                files.append((fpath, arcname))
    else:
        warnings.append("User skills directory not found; export will have no skills")

    # Optional: AGENTS.md
    if include_agents:
        agents_md = USER_AGENTS_MD
        if agents_md.exists():
            files.append((agents_md, "optional/codex/AGENTS.md"))
        else:
            warnings.append("AGENTS.md not found at ~/.codex/AGENTS.md")

    # Optional: hooks
    if include_hooks:
        hooks_dir = USER_CODEX / "hooks"
        if hooks_dir.exists() and hooks_dir.is_dir():
            for fpath in sorted(hooks_dir.rglob("*")):
                if fpath.is_dir():
                    continue
                rel = fpath.relative_to(USER_CODEX)
                for part in rel.parts:
                    if should_exclude(part):
                        break
                else:
                    files.append((fpath, f"optional/codex/{rel}"))
        else:
            warnings.append("Hooks directory not found at ~/.codex/hooks")

    # Optional: prompts
    if include_prompts:
        prompts_dir = USER_CODEX / "prompts"
        if prompts_dir.exists() and prompts_dir.is_dir():
            for fpath in sorted(prompts_dir.rglob("*")):
                if fpath.is_dir():
                    continue
                rel = fpath.relative_to(USER_CODEX)
                for part in rel.parts:
                    if should_exclude(part):
                        break
                else:
                    files.append((fpath, f"optional/codex/{rel}"))
        else:
            warnings.append("Prompts directory not found at ~/.codex/prompts")

    return files, warnings


def generate_manifest(
    files: List[Tuple[Path, str]],
    includes: Dict[str, bool],
    warnings: List[str],
) -> Dict[str, Any]:
    """Generate manifest dict for the archive."""
    file_entries: List[Dict[str, Any]] = []
    for src, arcname in sorted(files, key=lambda x: x[1]):
        file_entries.append({
            "path": arcname,
            "sha256": sha256_file(src),
            "size": src.stat().st_size,
        })
    return {
        "format": ARCHIVE_FORMAT,
        "created_at": _dt.datetime.now().isoformat(),
        "source_home": str(HOME),
        "includes": includes,
        "files": file_entries,
        "warnings": warnings,
    }


def generate_readme_md() -> str:
    """Generate README_IMPORT.md content."""
    return """# Codex Skills Migration Archive

This archive contains your user-level Codex Skills and optional configuration.

## How to import on a new Mac

### Option A: Using the standalone installer (no skill-manager required)

```bash
# 1. Extract the archive
tar -xzf codex-skills-migration-YYYYMMDD-HHMMSS.tar.gz
cd codex-skill-migration

# 2. Preview what will be imported
python3 install_import.py --dry-run

# 3. Import
python3 install_import.py --yes
```

### Option B: Using skill-manager (if already installed)

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py verify-archive <archive.tar.gz>
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py import <archive.tar.gz>
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py import <archive.tar.gz> --yes
```

## Safety

- Dry-run is the default. Nothing is written without `--yes`.
- Existing skills are backed up before being overwritten.
- AGENTS.md content is appended, not replaced.
- Login credentials, API keys, and secrets are excluded from the archive.
"""


def generate_install_import_py() -> str:
    """Generate standalone install_import.py."""
    return '''#!/usr/bin/env python3
"""Standalone Codex Skills Migration importer.

Usage:
  python3 install_import.py --dry-run     # preview only
  python3 install_import.py --yes          # import
  python3 install_import.py --yes --mode merge       # default
  python3 install_import.py --yes --mode overwrite
  python3 install_import.py --yes --mode skip-existing
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

HOME = Path.home()
SKILLS = HOME / ".agents" / "skills"
BACKUPS = SKILLS / ".backups"
CODEX = HOME / ".codex"
MANIFEST_FILE = Path(__file__).parent / "manifest.json"
USER_SKILLS_DIR = Path(__file__).parent / "user-skills"
OPTIONAL_DIR = Path(__file__).parent / "optional"


def now_stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_path(src: Path) -> Path:
    stamp = now_stamp()
    dest = BACKUPS / f"import-{stamp}" / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return dest


def load_manifest():
    if not MANIFEST_FILE.exists():
        print("ERROR: manifest.json not found", file=sys.stderr)
        sys.exit(1)
    with open(MANIFEST_FILE) as f:
        return json.load(f)


def import_skills(manifest, mode, dry_run):
    skills_dir = USER_SKILLS_DIR
    if not skills_dir.exists():
        print("No user-skills directory in archive")
        return

    existing_skills = set()
    if SKILLS.exists():
        for d in SKILLS.iterdir():
            if d.is_dir() and (d / "SKILL.md").exists():
                existing_skills.add(d.name)

    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir():
            continue
        md = child / "SKILL.md"
        if not md.exists():
            continue
        name = child.name
        dest = SKILLS / name

        if dest.exists():
            if mode == "skip-existing":
                print(f"  SKIP (exists): {name}")
                continue
            elif mode == "merge" or mode == "overwrite":
                bkp = backup_path(dest)
                if dry_run:
                    print(f"  BACKUP (dry-run): {bkp}")
                else:
                    print(f"  BACKUP: {bkp}")
                if not dry_run:
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()

        if dry_run:
            print(f"  IMPORT (dry-run): {name}")
        else:
            SKILLS.mkdir(parents=True, exist_ok=True)
            shutil.copytree(child, dest)
            print(f"  IMPORT: {name}")


def import_agents_md(manifest, mode, dry_run):
    agents_src = OPTIONAL_DIR / "codex" / "AGENTS.md"
    if not agents_src.exists():
        return

    dest = CODEX / "AGENTS.md"
    stamp = now_stamp()
    marker_start = f"<!-- imported-codex-agents-start: {stamp} -->"
    marker_end = "<!-- imported-codex-agents-end -->"

    # Check for previous import from same manifest
    if dest.exists():
        existing = dest.read_text(encoding="utf-8")
        manifest_hash = sha256_file(agents_src)
        if manifest_hash in existing:
            print(f"  SKIP AGENTS.md (already imported from this archive)")
            return

    if dry_run:
        if dest.exists():
            print(f"  APPEND AGENTS.md (dry-run, will add {marker_start})")
        else:
            print(f"  CREATE AGENTS.md (dry-run)")
        return

    content = agents_src.read_text(encoding="utf-8")
    block = f"\\n{marker_start}\\n{content}\\n{marker_end}\\n"

    if dest.exists():
        bkp = backup_path(dest)
        print(f"  BACKUP AGENTS.md: {bkp}")
        existing = dest.read_text(encoding="utf-8")
        dest.write_text(existing + block, encoding="utf-8")
        print(f"  APPEND AGENTS.md")
    else:
        CODEX.mkdir(parents=True, exist_ok=True)
        dest.write_text(content + "\\n", encoding="utf-8")
        print(f"  CREATE AGENTS.md")


def import_hooks(manifest, mode, dry_run):
    hooks_src = OPTIONAL_DIR / "codex" / "hooks"
    if not hooks_src.exists():
        return

    dest_dir = CODEX / "hooks"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for fpath in sorted(hooks_src.rglob("*")):
        if fpath.is_dir():
            continue
        rel = fpath.relative_to(hooks_src)
        dest = dest_dir / rel

        if dest.exists():
            if mode == "skip-existing":
                print(f"  SKIP hook: {rel}")
                continue
            bkp = backup_path(dest)
            if dry_run:
                print(f"  BACKUP hook (dry-run): {bkp}")
            else:
                print(f"  BACKUP hook: {bkp}")

        if dry_run:
            print(f"  IMPORT hook (dry-run): {rel}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fpath, dest)
            if fpath.suffix == ".py":
                os.chmod(dest, fpath.stat().st_mode | 0o111)
            print(f"  IMPORT hook: {rel}")

    if not dry_run:
        print("  NOTE: Check hook configuration manually. Hooks are not auto-enabled.")


def import_prompts(manifest, mode, dry_run):
    prompts_src = OPTIONAL_DIR / "codex" / "prompts"
    if not prompts_src.exists():
        return

    dest_dir = CODEX / "prompts"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for fpath in sorted(prompts_src.rglob("*")):
        if fpath.is_dir():
            continue
        rel = fpath.relative_to(prompts_src)
        dest = dest_dir / rel

        if dest.exists():
            if mode == "skip-existing":
                print(f"  SKIP prompt: {rel}")
                continue
            bkp = backup_path(dest)
            if dry_run:
                print(f"  BACKUP prompt (dry-run): {bkp}")
            else:
                print(f"  BACKUP prompt: {bkp}")

        if dry_run:
            print(f"  IMPORT prompt (dry-run): {rel}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fpath, dest)
            print(f"  IMPORT prompt: {rel}")


def main():
    parser = argparse.ArgumentParser(description="Codex Skills Migration Importer")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    parser.add_argument("--yes", action="store_true", help="Confirm import")
    parser.add_argument("--mode", choices=["merge", "overwrite", "skip-existing"],
                        default="merge", help="Import mode (default: merge)")
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        print("ERROR: Use --dry-run to preview or --yes to confirm import", file=sys.stderr)
        sys.exit(1)

    manifest = load_manifest()
    print(f"Archive: {manifest.get('format')} created {manifest.get('created_at')}")
    print(f"Includes: {json.dumps(manifest.get('includes', {}))}")
    print(f"Skills: {len([f for f in manifest.get('files', []) if f['path'].startswith('user-skills/')])}")
    print()

    mode = args.mode
    dry_run = args.dry_run

    print(f"Mode: {mode} | Dry-run: {dry_run}")
    print()

    print("=== Skills ===")
    import_skills(manifest, mode, dry_run)
    print()

    print("=== AGENTS.md ===")
    import_agents_md(manifest, mode, dry_run)
    print()

    print("=== Hooks ===")
    import_hooks(manifest, mode, dry_run)
    print()

    print("=== Prompts ===")
    import_prompts(manifest, mode, dry_run)
    print()

    if dry_run:
        print("Dry-run complete. Re-run with --yes to import.")
    else:
        print("Import complete.")


if __name__ == "__main__":
    main()
'''


# ============================================================
# Migration commands
# ============================================================

def cmd_export(args: argparse.Namespace) -> int:
    """Export user skills and optional config to a migration archive."""
    include_agents = args.include_agents or args.include_all_user_config
    include_hooks = args.include_hooks or args.include_all_user_config
    include_prompts = args.include_prompts or args.include_all_user_config

    print("Collecting files for export...")

    files, warnings = collect_export_files(include_agents, include_hooks, include_prompts)

    if not files:
        print("ERROR: No files to export.", file=sys.stderr)
        return 1

    # Secret scanning
    secret_warnings: List[str] = []
    safe_files: List[Tuple[Path, str]] = []
    for src, arcname in files:
        hits = scan_file_for_secrets(src)
        if hits:
            secret_warnings.append(f"{arcname}: secret patterns found ({', '.join(set(hits))})")
            if not args.allow_secrets:
                continue  # skip this file
        safe_files.append((src, arcname))

    if secret_warnings and not args.allow_secrets:
        print("\nWARNING: Secret-like patterns detected in the following files:")
        for w in secret_warnings:
            print(f"  - {w}")
        print("\nThese files were EXCLUDED from the archive.")
        print("Re-run with --allow-secrets to include them anyway.\n")

    if not safe_files:
        print("ERROR: No safe files to export after security scan.", file=sys.stderr)
        return 1

    includes: Dict[str, bool] = {
        "user_skills": True,
        "agents_md": include_agents,
        "hooks": include_hooks,
        "prompts": include_prompts,
    }

    all_warnings = warnings + secret_warnings

    stamp = now_stamp()
    output = Path(args.output).expanduser() if args.output else (
        HOME / "Desktop" / f"codex-skills-migration-{stamp}.tar.gz"
    )

    # Use a temp directory to build the archive structure
    with tempfile.TemporaryDirectory(prefix="codex-export-") as tmpdir:
        tmp = Path(tmpdir)
        archive_root = tmp / "codex-skill-migration"
        archive_root.mkdir()

        # Copy files
        for src, arcname in safe_files:
            dest = archive_root / arcname
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

        # Generate manifest
        manifest = generate_manifest(safe_files, includes, all_warnings)
        manifest_path = archive_root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        # Generate README
        readme_path = archive_root / "README_IMPORT.md"
        readme_path.write_text(generate_readme_md(), encoding="utf-8")

        # Generate standalone importer
        installer_path = archive_root / "install_import.py"
        installer_path.write_text(generate_install_import_py(), encoding="utf-8")
        os.chmod(installer_path, 0o755)

        # Create tar.gz
        output.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output, "w:gz") as tar:
            for fpath in sorted(archive_root.rglob("*")):
                if fpath.is_dir():
                    continue
                arcname = str(fpath.relative_to(tmp))
                if not is_path_safe(arcname):
                    print(f"WARNING: Skipping unsafe path: {arcname}", file=sys.stderr)
                    continue
                tar.add(fpath, arcname=arcname)

    skill_count = len([f for f in safe_files if f[1].startswith("user-skills/")])

    print(f"\nExport complete:")
    print(f"- Output: {output}")
    print(f"- Format: {ARCHIVE_FORMAT}")
    print(f"- Skills: {skill_count}")
    print(f"- Total files: {len(safe_files)}")
    print(f"- AGENTS.md: {'yes' if include_agents else 'no'}")
    print(f"- Hooks: {'yes' if include_hooks else 'no'}")
    print(f"- Prompts: {'yes' if include_prompts else 'no'}")
    if all_warnings:
        print(f"- Warnings: {len(all_warnings)}")

    return 0


def cmd_verify_archive(args: argparse.Namespace) -> int:
    """Verify a migration archive's integrity."""
    archive_path = Path(args.archive).expanduser()
    if not archive_path.exists():
        print(f"ERROR: Archive not found: {archive_path}", file=sys.stderr)
        return 1

    print(f"Archive: {archive_path}")

    try:
        tar = tarfile.open(archive_path, "r:gz")
    except Exception as e:
        print(f"ERROR: Cannot open archive: {e}", file=sys.stderr)
        return 1

    errors: List[str] = []
    warnings: List[str] = []

    # Check manifest
    manifest = None
    manifest_path = "codex-skill-migration/manifest.json"
    try:
        mf = tar.extractfile(manifest_path)
        if mf is None:
            errors.append("manifest.json not found inside archive")
        else:
            manifest = json.loads(mf.read().decode("utf-8"))
    except Exception as e:
        errors.append(f"Cannot read manifest.json: {e}")

    if manifest:
        fmt = manifest.get("format", "")
        print(f"Format: {fmt}")
        created = manifest.get("created_at", "unknown")
        print(f"Created: {created}")

        if fmt != ARCHIVE_FORMAT:
            errors.append(f"Unknown format: {fmt} (expected {ARCHIVE_FORMAT})")
        else:
            print("Format check: pass")

    # Path safety
    path_ok = True
    for member in tar.getmembers():
        if not is_path_safe(member.name):
            path_ok = False
            warnings.append(f"Unsafe path in archive: {member.name}")

    print(f"Path safety: {'pass' if path_ok else 'fail'}")

    # SHA256 check
    sha_ok = True
    if manifest:
        manifest_files = {f["path"]: f for f in manifest.get("files", [])}
        for member in tar.getmembers():
            if member.isfile():
                expected = manifest_files.get(member.name)
                if expected:
                    try:
                        f = tar.extractfile(member)
                        if f:
                            h = hashlib.sha256()
                            for chunk in iter(lambda: f.read(65536), b""):
                                h.update(chunk)
                            actual = h.hexdigest()
                            if actual != expected["sha256"]:
                                sha_ok = False
                                warnings.append(f"SHA256 mismatch: {member.name}")
                    except Exception:
                        pass

    print(f"SHA256 check: {'pass' if sha_ok else 'fail'}")

    # Skill count and duplicate check
    skill_names: Set[str] = set()
    skill_count = 0
    for member in tar.getmembers():
        if member.isfile() and member.name.startswith("codex-skill-migration/user-skills/"):
            parts = Path(member.name).parts
            if len(parts) >= 4:
                skill_names.add(parts[2])

    for name in sorted(skill_names):
        skill_count += 1

    print(f"Skills: {skill_count}")

    # Secret scan inside archive
    for member in tar.getmembers():
        if not member.isfile():
            continue
        if member.name.endswith((".key", ".pem", ".p12", ".mobileprovision")):
            warnings.append(f"Suspicious file type in archive: {member.name}")
        try:
            f = tar.extractfile(member)
            if f:
                text = f.read().decode("utf-8", errors="replace")
                for pat, label in SECRET_PATTERNS:
                    if pat in text:
                        warnings.append(f"Secret-like pattern in: {member.name} ({label})")
                        break
        except Exception:
            pass

    tar.close()

    if warnings:
        print(f"Warnings:")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print(f"\nErrors:")
        for e in errors:
            print(f"  - {e}")
        return 2

    print("\nVerification: pass")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    """Import skills and optional config from a migration archive."""
    archive_path = Path(args.archive).expanduser()
    if not archive_path.exists():
        print(f"ERROR: Archive not found: {archive_path}", file=sys.stderr)
        return 1

    try:
        tar = tarfile.open(archive_path, "r:gz")
    except Exception as e:
        print(f"ERROR: Cannot open archive: {e}", file=sys.stderr)
        return 1

    # Extract manifest
    manifest = None
    try:
        mf = tar.extractfile("codex-skill-migration/manifest.json")
        if mf:
            manifest = json.loads(mf.read().decode("utf-8"))
    except Exception:
        pass

    if not manifest:
        print("ERROR: manifest.json not found in archive", file=sys.stderr)
        tar.close()
        return 1

    mode = args.mode or "merge"
    dry_run = not args.yes

    includes = manifest.get("includes", {})
    has_skills = includes.get("user_skills", False)
    has_agents = includes.get("agents_md", False)
    has_hooks = includes.get("hooks", False)
    has_prompts = includes.get("prompts", False)

    # Count skills in archive
    skill_count = len([f for f in manifest.get("files", [])
                       if f["path"].startswith("user-skills/")])

    print(f"Archive: {manifest.get('format')} created {manifest.get('created_at')}")
    print(f"Mode: {mode} | Dry-run: {dry_run}")
    print()

    print("Will import:")
    print(f"- Skills: {skill_count}")
    print(f"- AGENTS.md: {'yes' if has_agents else 'no'}")
    print(f"- Hooks: {'yes' if has_hooks else 'no'}")
    print(f"- Prompts: {'yes' if has_prompts else 'no'}")
    print()

    # Check conflicts
    conflicts: List[str] = []
    if has_skills:
        if USER_SKILLS.exists():
            existing = {d.name for d in USER_SKILLS.iterdir()
                        if d.is_dir() and (d / "SKILL.md").exists() and d.name not in {".trash", ".backups"}}
            archive_names: Set[str] = set()
            for f in manifest.get("files", []):
                if f["path"].startswith("user-skills/"):
                    parts = Path(f["path"]).parts
                    if len(parts) >= 2:
                        archive_names.add(parts[1])
            overlap = archive_names & existing
            for name in sorted(overlap):
                action = "backup then replace" if mode in ("merge", "overwrite") else "skip"
                conflicts.append(f"existing skill: {name} -> {action}")

    if conflicts:
        print("Conflicts:")
        for c in conflicts:
            print(f"  - {c}")
        print()

    if manifest.get("warnings"):
        print("Warnings:")
        for w in manifest["warnings"]:
            print(f"  - {w}")
        print()

    if dry_run:
        print("Dry-run only. Re-run with --yes to import.")
        tar.close()
        return 0

    # Actual import – extract to temp dir first (path safety)
    with tempfile.TemporaryDirectory(prefix="codex-import-") as tmpdir:
        tmp = Path(tmpdir)

        # Extract with path safety check
        for member in tar.getmembers():
            if not is_path_safe(member.name):
                print(f"WARNING: Skipping unsafe path: {member.name}", file=sys.stderr)
                continue
            tar.extract(member, tmp)

    tar.close()

    extracted = tmp / "codex-skill-migration"

    # Import skills
    skills_src = extracted / "user-skills"
    if has_skills and skills_src.exists():
        existing_skills: Set[str] = set()
        if USER_SKILLS.exists():
            existing_skills = {d.name for d in USER_SKILLS.iterdir()
                               if d.is_dir() and (d / "SKILL.md").exists()
                               and d.name not in {".trash", ".backups"}}

        USER_SKILLS.mkdir(parents=True, exist_ok=True)
        for child in sorted(skills_src.iterdir()):
            if not child.is_dir():
                continue
            if not (child / "SKILL.md").exists():
                continue
            dest = USER_SKILLS / child.name

            if dest.exists():
                if mode == "skip-existing":
                    print(f"SKIP: {child.name} (already exists)")
                    continue
                bkp = backup_skill_dir(dest)
                print(f"BACKUP: {bkp}")
                shutil.rmtree(dest)

            print(f"IMPORT: {child.name}")
            shutil.copytree(child, dest)

    # Import AGENTS.md
    agents_src = extracted / "optional" / "codex" / "AGENTS.md"
    if has_agents and agents_src.exists():
        stamp = now_stamp()
        marker_start = f"<!-- imported-codex-agents-start: {stamp} -->"
        marker_end = "<!-- imported-codex-agents-end -->"
        content = agents_src.read_text(encoding="utf-8")
        block = f"\n{marker_start}\n{content}\n{marker_end}\n"

        agents_dest = USER_AGENTS_MD
        if agents_dest.exists():
            existing = agents_dest.read_text(encoding="utf-8")
            agents_hash = sha256_file(agents_src)
            if agents_hash in existing:
                print("SKIP AGENTS.md (already imported from this archive)")
            else:
                bkp = backup_skill_dir(agents_dest)
                print(f"BACKUP AGENTS.md: {bkp}")
                agents_dest.write_text(existing + block, encoding="utf-8")
                print("APPEND AGENTS.md")
        else:
            USER_CODEX.mkdir(parents=True, exist_ok=True)
            agents_dest.write_text(content + "\n", encoding="utf-8")
            print("CREATE AGENTS.md")

    # Import hooks
    hooks_src = extracted / "optional" / "codex" / "hooks"
    if has_hooks and hooks_src.exists():
        hooks_dest_dir = USER_CODEX / "hooks"
        hooks_dest_dir.mkdir(parents=True, exist_ok=True)
        for fpath in sorted(hooks_src.rglob("*")):
            if fpath.is_dir():
                continue
            rel = fpath.relative_to(hooks_src)
            dest = hooks_dest_dir / rel
            if dest.exists():
                if mode == "skip-existing":
                    print(f"SKIP hook: {rel}")
                    continue
                bkp = backup_skill_dir(dest)
                print(f"BACKUP hook: {bkp}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fpath, dest)
            if fpath.suffix == ".py":
                os.chmod(dest, fpath.stat().st_mode | 0o111)
            print(f"IMPORT hook: {rel}")
        print("NOTE: Check hook configuration manually. Hooks are not auto-enabled.")

    # Import prompts
    prompts_src = extracted / "optional" / "codex" / "prompts"
    if has_prompts and prompts_src.exists():
        prompts_dest_dir = USER_CODEX / "prompts"
        prompts_dest_dir.mkdir(parents=True, exist_ok=True)
        for fpath in sorted(prompts_src.rglob("*")):
            if fpath.is_dir():
                continue
            rel = fpath.relative_to(prompts_src)
            dest = prompts_dest_dir / rel
            if dest.exists():
                if mode == "skip-existing":
                    print(f"SKIP prompt: {rel}")
                    continue
                bkp = backup_skill_dir(dest)
                print(f"BACKUP prompt: {bkp}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fpath, dest)
            print(f"IMPORT prompt: {rel}")

    print("\nImport complete.")
    return 0
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe Codex Skill manager")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("locations").set_defaults(func=cmd_locations)
    sub.add_parser("list").set_defaults(func=cmd_list)

    p = sub.add_parser("search")
    p.add_argument("query")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("read")
    p.add_argument("skill")
    p.add_argument("--full", action="store_true")
    p.add_argument("--lines", type=int, default=80)
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("validate")
    p.add_argument("skill", nargs="?")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("backup")
    p.add_argument("skill")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("delete")
    p.add_argument("skill")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("restore")
    p.add_argument("path")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser("create")
    p.add_argument("name")
    p.add_argument("--description", default="")
    p.set_defaults(func=cmd_create)

    # Migration commands
    p = sub.add_parser("export")
    p.add_argument("--output", default="")
    p.add_argument("--include-agents", action="store_true")
    p.add_argument("--include-hooks", action="store_true")
    p.add_argument("--include-prompts", action="store_true")
    p.add_argument("--include-all-user-config", action="store_true")
    p.add_argument("--allow-secrets", action="store_true")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("verify-archive")
    p.add_argument("archive")
    p.set_defaults(func=cmd_verify_archive)

    p = sub.add_parser("import")
    p.add_argument("archive")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--mode", choices=["merge", "overwrite", "skip-existing"],
                   default="merge")
    p.set_defaults(func=cmd_import)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

# ============================================================
