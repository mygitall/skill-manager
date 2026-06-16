# Skill Manager — Quick Reference

Full documentation: [README.md](../README.md)

## Quick commands

```bash
SCRIPT=~/.agents/skills/skill-manager/scripts/skillctl.py

# View
$SCRIPT list                     # list all skills
$SCRIPT search <keyword>         # search by keyword
$SCRIPT read <name>              # read first 80 lines
$SCRIPT locations                # show managed dirs

# Validate
$SCRIPT validate --all           # validate all skills
$SCRIPT validate <name>          # validate one skill

# Manage
$SCRIPT create <name> --description "..."   # create new skill
$SCRIPT backup <name>                        # backup skill
$SCRIPT delete <name>                        # dry-run delete
$SCRIPT delete <name> --yes                  # safe delete (backup + trash)
$SCRIPT restore <path> --yes                 # restore from trash/backup

# Migration
$SCRIPT export                                # export skills only
$SCRIPT export --include-all-user-config      # export everything
$SCRIPT verify-archive <file.tar.gz>          # verify archive
$SCRIPT import <file.tar.gz>                  # dry-run import
$SCRIPT import <file.tar.gz> --yes            # confirm import

# Version
$SCRIPT --version                  # skillctl.py 1.0.0
```

## Codex shortcuts

```
$skill-manager list all skills
/prompts:skili search <keyword>
```

## Safety defaults

- Delete: backup first, then move to `.trash/`, requires `--yes`
- Import: dry-run by default, `--yes` to write
- Export: secret scan excludes sensitive files
