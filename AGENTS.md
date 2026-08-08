# AGENTS.md

## Agent Skills

- Before responding or acting, inspect the skills available in the current agent runtime.
- If the user names a skill, or the request matches a skill's `description`, read the complete `SKILL.md` before taking action and follow it.
- Repository skills use the open Agent Skills format: `.agents/skills/<skill-name>/SKILL.md` with portable `name` and `description` frontmatter.
- Expose the same skill directory to Claude Code at `.claude/skills/<skill-name>`, preferably with a symlink. Existing Claude-native skills may remain physically in `.claude/skills` when `.agents/skills` links to that exact directory. Never maintain divergent copies.
- Keep portable `SKILL.md` frontmatter limited to Agent Skills fields. Put runtime-specific configuration in runtime-specific files such as `agents/openai.yaml`.
- If a required skill cannot be loaded, state the problem briefly and use the safest available fallback.

Project memory has moved to `.claude/CLAUDE.md` and `.claude/rules/` (core, gcp, git-workflow).
