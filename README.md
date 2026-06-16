# Codex Skill Manager (`skill-manager`) 完整使用手册

## 概述

`skill-manager` 是一个本地 Codex Skill 管理器，提供完整的 CRUD 操作、安全删除/恢复、以及跨机器迁移功能。

- **脚本路径**: `~/.agents/skills/skill-manager/scripts/skillctl.py`
- **Codex 内调用**: `$skill-manager <操作>`
- **快捷 prompt**: `/prompts:skili`

> 所有操作默认安全：删除前先备份，导入前先 dry-run，覆盖前先备份已有文件。

---

---

## 前置要求

- **Python 3.8+**（无外部依赖，仅用标准库）
- **tar**（macOS/Linux 自带）
- **Git**（可选，用于版本控制）

---

## 安装

### 方式 A：从 GitHub 克隆（推荐）

```bash
git clone https://github.com/mygitall/skill-manager.git
cd skill-manager
bash install.sh
```

### 方式 B：手动安装

```bash
mkdir -p ~/.agents/skills
cp -r skill-manager ~/.agents/skills/
chmod +x ~/.agents/skills/skill-manager/scripts/skillctl.py
```

### 验证安装

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py --version
# skillctl.py 1.0.0

python3 ~/.agents/skills/skill-manager/scripts/skillctl.py list
```

---

## 一、查看类命令

---

### 1. `list` — 列出所有 Skill

列出当前管理的所有 Skill，包括名称、作用域、校验状态、路径和描述摘要。

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py list
```

**输出格式**:
```
Skills:
- <name> | <scope> | valid=<yes/no> | <path> | <description>
```

**Codex 内调用**: `$skill-manager list all skills`

---

### 2. `search` — 按关键词搜索

在 Skill 名称、目录名、描述和路径中搜索匹配项（大小写不敏感）。

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py search <关键词>
```

**示例**:
```bash
skillctl.py search token
skillctl.py search ppt
```

**Codex 内调用**: `$skill-manager search token`

---

### 3. `read` — 查看 Skill 内容

查看指定 Skill 的元数据（name、description、path）和正文前 80 行。

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py read <skill名称>
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py read <skill名称> --full        # 完整内容
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py read <skill名称> --lines 30   # 指定行数
```

**Codex 内调用**: `$skill-manager read token-saver`

---

### 4. `locations` — 查看管理的目录

显示当前扫描的 Skill 目录及其是否存在。

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py locations
```

**管理范围**:
- `user`: `~/.agents/skills`（用户级）
- `repo`: 当前目录到 Git 根目录的 `.agents/skills`（项目级）
- 不管理系统级/管理员级 Skill

---

## 二、校验类命令

---

### 5. `validate` — 校验 Skill 合法性

检查 SKILL.md 是否满足最低要求：存在 YAML frontmatter、有 `name`、有 `description`、有正文。

同时扫描危险模式（如 `rm -rf /`、`curl | sh` 等）。

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py validate <skill名称>
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py validate --all                # 校验全部
```

**校验规则**:
| 检查项 | 严重程度 |
|---|---|
| SKILL.md 缺失 | 无效 |
| 缺少 YAML frontmatter | 无效 |
| 缺少 name | 无效 |
| 缺少 description | 无效 |
| 缺少正文内容 | 无效 |
| description 超过 400 字符 | 警告 |
| 包含危险 shell 模式 | 警告 |

**Codex 内调用**: `$skill-manager validate --all`

---

## 三、管理类命令

---

### 6. `create` — 创建新 Skill

在 `~/.agents/skills/` 下创建新 Skill 目录和 SKILL.md 模板。

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py create <skill名称>
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py create my-skill --description "Use when working with Foo."
```

**命名规则**: 仅允许 `[a-zA-Z0-9][a-zA-Z0-9._-]*`，不能以 `.` 开头，不能含 `/` 或 `\`。

创建后自动校验，输出校验结果。

**Codex 内调用**: `$skill-manager create my-skill`

---

### 7. `backup` — 备份 Skill

将指定 Skill 复制到 `~/.agents/skills/.backups/<name>-<时间戳>/`。

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py backup <skill名称>
```

**Codex 内调用**: `$skill-manager backup token-saver`

---

### 8. `delete` — 安全删除 Skill

**默认行为**（不加 `--yes`）：dry-run，只显示将要执行的操作，不真正删除。

**确认删除**（加 `--yes`）：
1. 先创建备份到 `~/.agents/skills/.backups/`
2. 再移动到 `~/.agents/skills/.trash/<name>-<时间戳>/`
3. 不永久删除

```bash
# 预览（不实际执行）
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py delete <skill名称>

# 确认删除
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py delete <skill名称> --yes
```

**安全说明**:
- 必须先备份再移动
- 不删除项目级 Skill（除非明确指定路径）
- 可随时用 `restore` 恢复

**Codex 内调用**: `$skill-manager delete my-skill`

---

### 9. `restore` — 恢复已删除/备份的 Skill

从 `.trash/` 或 `.backups/` 中恢复 Skill 到 `~/.agents/skills/`。

```bash
# 预览
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py restore <trash或backup路径>

# 确认恢复
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py restore <trash或backup路径> --yes
```

**行为**:
- 自动去除时间戳后缀恢复原始名称
- 如果目标已存在 Skill，先备份已有 Skill 再覆盖
- 不加 `--yes` 为 dry-run

**示例**:
```bash
skillctl.py restore ~/.agents/skills/.trash/token-saver-20260616-114759 --yes
```

---

## 四、迁移类命令

---

### 10. `export` — 导出迁移包

将所有用户级 Skill（及可选的 AGENTS.md、hooks、prompts）打包为 tar.gz 迁移档案。

```bash
# 仅导出 Skills（默认）
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py export

# 指定输出路径
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py export --output ~/Desktop/my-skills.tar.gz

# 导出 Skills + AGENTS.md
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py export --include-agents

# 导出 Skills + hooks
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py export --include-hooks

# 导出 Skills + prompts
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py export --include-prompts

# 一键导出全部（Skills + AGENTS.md + hooks + prompts）
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py export --include-all-user-config

# 允许包含疑似密钥的文件（默认排除）
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py export --include-all-user-config --allow-secrets
```

**默认输出路径**: `~/Desktop/codex-skills-migration-<时间戳>.tar.gz`

**默认排除项**:
| 类型 | 示例 |
|---|---|
| 临时文件 | `.trash`, `.backups`, `*.tmp`, `*.log` |
| 系统文件 | `.DS_Store`, `__pycache__`, `*.pyc` |
| 敏感文件 | `.env`, `.env.*`, `*.key`, `*.pem`, `*.p12`, `*.mobileprovision` |
| 疑似密钥内容 | 包含 `sk-`、`api_key`、`SECRET`、`TOKEN`、`PRIVATE KEY` 等模式的文件 |

**导出包结构**:
```
codex-skill-migration/
├── manifest.json          # 清单文件（含 SHA256）
├── README_IMPORT.md       # 导入说明
├── install_import.py      # 独立导入脚本（无需 skill-manager）
├── user-skills/           # 用户 Skill
│   ├── token-saver/
│   │   └── SKILL.md
│   └── skill-manager/
│       ├── SKILL.md
│       ├── scripts/
│       └── references/
└── optional/              # 可选配置（仅当 --include-* 时存在）
    └── codex/
        ├── AGENTS.md
        ├── hooks/
        └── prompts/
```

---

### 11. `verify-archive` — 校验迁移包

在导入前验证迁移包的完整性。

```bash
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py verify-archive <archive.tar.gz>
```

**校验项目**:

| 检查项 | 说明 |
|---|---|
| tar.gz 可读性 | 确保文件未损坏 |
| manifest.json 存在 | 必须包含清单文件 |
| 格式版本 | 必须为 `codex-skill-migration-v1` |
| SHA256 匹配 | 每个文件的哈希值与 manifest 一致 |
| 路径安全 | 不允许 `../`、绝对路径、`~` |
| 可疑文件类型 | 检测 `.key`、`.pem`、`.p12` 等 |
| 密钥内容扫描 | 扫描包内文件是否含敏感模式 |
| Skill 数量 | 统计 user-skills 下的 Skill 数 |

**输出示例**:
```
Archive: ~/Desktop/codex-skills-migration-20260616-115322.tar.gz
Format: codex-skill-migration-v1
Created: 2026-06-16T11:53:22
Format check: pass
Path safety: pass
SHA256 check: pass
Skills: 3
Verification: pass
```

---

### 12. `import` — 导入迁移包

从迁移包恢复 Skill 和可选配置到当前机器。

```bash
# 预览（默认 dry-run，不写入）
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py import <archive.tar.gz>

# 确认导入（merge 模式）
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py import <archive.tar.gz> --yes

# overwrite 模式（先备份再覆盖全部）
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py import <archive.tar.gz> --yes --mode overwrite

# skip-existing 模式（已有 Skill 跳过）
python3 ~/.agents/skills/skill-manager/scripts/skillctl.py import <archive.tar.gz> --yes --mode skip-existing
```

**三种模式对比**:

| 模式 | 已存在 Skill | 新 Skill | AGENTS.md |
|---|---|---|---|
| `merge`（默认） | 备份 → 覆盖 | 直接导入 | 追加到末尾 |
| `overwrite` | 备份 → 覆盖 | 直接导入 | 备份 → 覆盖 |
| `skip-existing` | 跳过 | 直接导入 | 跳过 |

**导入行为细节**:
- **Skills**: 已有同名 Skill 会被备份到 `~/.agents/skills/.backups/import-<时间戳>/`，再覆盖
- **AGENTS.md**: 追加内容到 `~/.codex/AGENTS.md`，用 `<!-- imported-codex-agents-start: <时间戳> -->` 标记包裹；重复导入同一 manifest hash 会被跳过
- **Hooks**: 导入到 `~/.codex/hooks/`，同名文件先备份，`.py` 文件保留可执行权限；不自动启用，需手动检查配置
- **Prompts**: 导入到 `~/.codex/prompts/`，同名文件先备份

**新 Mac 无 skill-manager 时的导入方式**:
```bash
# 1. 解压
tar -xzf codex-skills-migration-YYYYMMDD-HHMMSS.tar.gz
cd codex-skill-migration

# 2. 预览
python3 install_import.py --dry-run

# 3. 导入
python3 install_import.py --yes
```

---

## 五、调用方式汇总

### 方式 A：命令行直接调用脚本

```bash
SCRIPT=~/.agents/skills/skill-manager/scripts/skillctl.py

$SCRIPT list
$SCRIPT search <关键词>
$SCRIPT read <skill名>
$SCRIPT validate <skill名>
$SCRIPT validate --all
$SCRIPT create <新skill名> --description "..."
$SCRIPT backup <skill名>
$SCRIPT delete <skill名>
$SCRIPT delete <skill名> --yes
$SCRIPT restore <路径>
$SCRIPT restore <路径> --yes
$SCRIPT locations
$SCRIPT export
$SCRIPT export --include-all-user-config
$SCRIPT verify-archive <archive.tar.gz>
$SCRIPT import <archive.tar.gz>
$SCRIPT import <archive.tar.gz> --yes
```

### 方式 B：Codex 对话中调用

在 Codex 对话框中输入 `$skill-manager` 开头的内容，Codex 会自动加载 skill-manager 并执行相应操作：

```
$skill-manager list all skills
$skill-manager search ppt
$skill-manager read token-saver
$skill-manager create my-tool
$skill-manager backup token-saver
$skill-manager delete old-skill
$skill-manager validate --all
```

### 方式 C：快捷 Prompt

在 Codex 对话框输入 `/prompts:skili` + 参数：

```
/prompts:skili list
/prompts:skili search token
/prompts:skili validate --all
```

---

## 六、安全机制总览

| 操作 | 安全措施 |
|---|---|
| 删除 Skill | 先备份到 `.backups/`，再移到 `.trash/`，需 `--yes` |
| 恢复 Skill | 目标已有同名 Skill 时先备份再覆盖，需 `--yes` |
| 导入 Skills | 默认 dry-run，已有 Skill 先备份再覆盖 |
| 导入 AGENTS.md | 追加不覆盖，带时间戳标记，防重复导入 |
| 导出 | 密钥扫描排除敏感文件，路径安全检测 |
| 校验 | 危险 shell 模式检测 |

**不迁移的内容**:
- Codex 登录状态 / session
- API Key、Token、密钥
- 系统级/管理员级 Skill
- 业务项目代码
