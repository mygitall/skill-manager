# Skill Manager Usage

Use this skill with:

```text
$skill-manager list all installed skills

Or use the helper script directly:

python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" list
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" locations
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" search token
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" read token-saver
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" validate --all
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" create my-skill --description "Use when ..."
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" backup token-saver
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" delete token-saver
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" delete token-saver --yes
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" restore "$HOME/.agents/skills/.trash/token-saver-YYYYMMDD-HHMMSS"
python3 "$HOME/.agents/skills/skill-manager/scripts/skillctl.py" restore "$HOME/.agents/skills/.trash/token-saver-YYYYMMDD-HHMMSS" --yes

Delete is safe by default:

Creates a backup.
Moves the skill to .trash.
Requires --yes for actual move.

The script manages:

user skills: $HOME/.agents/skills
repo skills: .agents/skills locations from the current directory up to the git root

It does not manage admin/system skills by default.

## Migration

### Old Mac: export skills only

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py export
```

### Old Mac: export everything (skills + AGENTS.md + hooks + prompts)

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py export --include-all-user-config
```

### New Mac: extract and preview

```bash
tar -xzf ~/Desktop/codex-skills-migration-YYYYMMDD-HHMMSS.tar.gz
cd codex-skill-migration
python3 install_import.py --dry-run
```

### New Mac: confirm import (standalone, no skill-manager needed)

```bash
python3 install_import.py --yes
```

### New Mac: using skill-manager (if already installed)

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py verify-archive ~/Desktop/codex-skills-migration-YYYYMMDD-HHMMSS.tar.gz
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py import ~/Desktop/codex-skills-migration-YYYYMMDD-HHMMSS.tar.gz
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py import ~/Desktop/codex-skills-migration-YYYYMMDD-HHMMSS.tar.gz --yes
```

### Import modes

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py import archive.tar.gz --mode merge --yes
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py import archive.tar.gz --mode overwrite --yes
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py import archive.tar.gz --mode skip-existing --yes
```
