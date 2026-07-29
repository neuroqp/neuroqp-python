# Using NeuroQP with AI coding agents

NeuroQP provides an optional agent skill for writing Python analyses of project exports. The skill gives an AI coding agent concise instructions for navigating exports, interpreting scientific results, processing images, and finding exact API documentation when needed.

Install the skill from the same Python environment as NeuroQP so its guidance matches the package version used by your analysis. Skill installation never updates the Python package, and the skill never updates itself automatically.

## Install the NeuroQP skill for Codex

From the root of your analysis project, run:

```
neuroqp skill install --agent codex
```

This installs the skill in `.agents/skills/neuroqp-python` for Codex to discover in the current project. To make the skill available to Codex across all your projects instead, use:

```
neuroqp skill install --agent codex --scope user
```

When a compatible skill update is available, Codex can mention it when the skill loads. Apply the update explicitly:

```
neuroqp skill update --agent codex
```

## Install the NeuroQP skill for Claude Code

From the root of your analysis project, run:

```
neuroqp skill install --agent claude
```

This installs the skill in `.claude/skills/neuroqp-python` for Claude Code to discover in the current project. To make the skill available to Claude Code across all your projects instead, use:

```
neuroqp skill install --agent claude --scope user
```

When a compatible skill update is available, Claude Code can mention it when the skill loads. Apply the update explicitly:

```
neuroqp skill update --agent claude
```

If you use both Codex and Claude Code, install or update both copies with `--agent all`.

## Use an AI coding agent without installing the skill

An AI coding agent can use the online AI-readable documentation without installing the NeuroQP skill. `llms.txt` is a concise index of the public documentation and links to expanded Markdown versions of every page. `llms-full.txt` contains the complete documentation in one file.

Copy this prompt into your AI coding agent and replace the final sentence with the analysis you want to build:

```
I am using NeuroQP Python to analyze a NeuroQP project export. First read https://python.neuroqp.com/llms.txt and use the Markdown pages linked from it as the authoritative reference. Check the NeuroQP Python version installed in this project and prefer matching versioned documentation when available. Use only the public NeuroQP API, preserve the documented scientific meaning and alignment of exported data, and do not invent unavailable transformations or metadata.

Help me write an analysis that [describe the analysis you want to perform].
```

The online documentation is sufficient when you prefer not to install agent-specific files. The installed skill is more convenient for repeated NeuroQP work because its essential workflow loads automatically when the agent recognizes a relevant task.
