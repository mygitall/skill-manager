---
name: skill-manager
description: Use to manage installed Codex skills. Supports listing, searching, reading, validating, creating, editing, backing up, deleting, and restoring user-level or repo-level skills safely.
---

# Skill Manager

This skill manages local Codex Skills safely.

It can help with:

- list installed skills;
- search skills by name or description;
- read a skill;
- validate SKILL.md frontmatter;
- create a new skill;
- edit an existing skill;
- backup a skill;
- delete a skill safely;
- restore a backed-up skill;
- show skill locations;
- generate usage commands.

Safety is more important than convenience.

---

## Supported skill locations

Manage these locations by default:

1. User-level skills:
   - `$HOME/.agents/skills`

2. Repo/project-level skills:
   - `.agents/skills`
   - parent `.agents/skills` locations up to the repository root when relevant

Read-only or dangerous locations should not be modified unless the user explicitly asks and the path is writable.

Do not modify system-level or admin-level skills by default.

---

## Core rules

When this skill is active:

- Be concise.
- Prefer using `scripts/skillctl.py` for actual operations.
- Always show what will be changed before changing it.
- Never permanently delete a skill without backup.
- Never overwrite an existing skill without creating a backup first.
- Never edit unrelated files.
- Never install dependencies.
- Never use network access.
- Never modify business project code.
- Validate frontmatter after creating or editing `SKILL.md`.
- Prefer safe rename/move operations over destructive deletion.

---

## CRUD behavior

### List

When the user asks to list all skills:

- scan supported skill directories;
- find folders containing `SKILL.md`;
- parse `name` and `description`;
- show scope, path, validity, and backup status;
- keep output compact.

### Read

When the user asks to view a skill:

- show name, description, path, and first relevant sections;
- do not dump huge files unless asked;
- if the file is long, summarize structure first.

### Create

When creating a new skill:

- create a folder under `$HOME/.agents/skills/<skill-name>` by default;
- create `SKILL.md`;
- include valid YAML frontmatter;
- keep description short and trigger-focused;
- do not create complex scripts unless needed.

### Update

When updating a skill:

- create a timestamped backup first;
- edit the smallest necessary part;
- validate `SKILL.md`;
- show changed files and verification result.

### Delete

When deleting a skill:

- never use permanent deletion first;
- create a timestamped backup;
- move the skill to:
  `$HOME/.agents/skills/.trash/<skill-name>-<timestamp>`
- confirm the final trash path;
- do not delete repo skills unless user explicitly requested that exact path.

### Restore

When restoring:

- list available backups or trash entries;
- restore to the original or user-specified location;
- do not overwrite an existing skill without backing it up.

---

## Dangerous operations

Before any destructive operation, show:

```text
Operation:
Target:
Backup path:
Risk:

Then proceed only if the user's request is explicit enough.

If ambiguous, ask for the exact skill name or path.

Validation rules

A valid skill must have:

a directory;
a SKILL.md file;
YAML frontmatter;
name;
description;
non-empty instructions.

Warn if:

description is too long;
description is vague;
duplicate skill names exist;
skill has no clear trigger;
skill contains dangerous shell commands;
skill is located in an unexpected path.
Output format

Default response format:

Skills:
- name | scope | status | path | description

Actions:
- list
- read <name>
- create <name>
- edit <name>
- backup <name>
- delete <name>
- restore <name>
- validate <name/all>

For completed operations:

Done:
- ...

Changed:
- ...

Backup:
- ...

Validation:
- ...

Next:
- ...

Keep output concise.
Do not paste full files unless requested.

Preferred commands

Use the helper script:

python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" list
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" search <keyword>
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" read <skill-name>
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" validate <skill-name|--all>
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" backup <skill-name>
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" delete <skill-name>
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" restore <trash-folder-or-backup-path>
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" locations

If the helper script is missing or broken, inspect files manually with safe shell commands.

---

## Migration

The skill-manager supports safe migration of user-level Skills across machines.

### Export

Export all user skills (and optionally AGENTS.md, hooks, prompts) into a portable tar.gz archive:

```text
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py export
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py export --include-all-user-config
```

The export:
- Includes all user skills from `$HOME/.agents/skills`.
- Excludes `.trash`, `.backups`, temp files, and known secret-file extensions.
- Scans files for API keys / tokens and excludes them unless `--allow-secrets` is given.
- Generates `manifest.json` with SHA256 hashes.
- Generates standalone `install_import.py` so import works on a new machine even without skill-manager installed.

### Import

Import a migration archive into the current machine:

```text
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py import <archive.tar.gz>
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py import <archive.tar.gz> --yes
```

Import modes:
- `merge` (default): import new skills; backup then replace existing ones.
- `overwrite`: backup all existing, then replace.
- `skip-existing`: skip skills that already exist.

Import behavior:
- Default is dry-run; nothing is written without `--yes`.
- Existing skills are backed up to `$HOME/.agents/skills/.backups/import-<timestamp>/` before being overwritten.
- AGENTS.md content is appended with timestamped markers, never fully replaced.
- Hooks and prompts are backed up before overwriting.
- A standalone `install_import.py` is also included in every export for machines without skill-manager.

### Verify

Verify a migration archive before importing:

```text
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py verify-archive <archive.tar.gz>
```

Checks:
- Archive integrity (tar.gz readable).
- `manifest.json` exists and format matches `codex-skill-migration-v1`.
- SHA256 hashes match for every file.
- Path safety (no `../`, absolute paths, or `~`).
- No suspicious file types (`.key`, `.pem`, `.p12`).
- Secret pattern scan inside archive.

### What migration does NOT include

- Codex login state or session tokens.
- API keys, secrets, or private keys (actively excluded).
- System-level or admin-level Skills.
- Business project code.
