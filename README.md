# Recruiting Tools

To use:
* open your terminal ("Terminal" app in MacOS),
* copy `[ ! -d "git_recruiting" ] &&https://github.com/arames/git_recruiting.git git_recruiting`
* run the tool: ./git_recruiting/gitcontrib.py


An example session looks like
```
Loaded options from /Volumes/work/tmp/.git-contributor-options.json

============================================================
Git Contributor Analysis - Interactive Mode
============================================================

(Options loaded from .git-contributor-options.json)

Current Configuration:
  1. Repository URL: https://github.com/llvm/llvm-project.git
  2. Subdirectory: mlir
  3. Branch: HEAD
  4. Since date: 2025-10-01
  5. Until date: (now)
  6. Output file: contributors.csv
  7. Output format: numbers
  8. Include LinkedIn: True
  9. Cache directory: /Users/arames/.local/share/git-contributor-analyzer

  r. Run Analysis
  s. Save options and exit
  0. Exit without saving

Select option (0-9, r, s): r
Options saved to /Volumes/work/tmp/.git-contributor-options.json
Updating cached repository at /Users/arames/.local/share/git-contributor-analyzer/llvm-project_778bf569aafe...

Analyzing contributors...
Analyzing commits with command: git log HEAD --no-merges --format=%H|%an|%ae|%at --since=2025-01-01 -- mlir

Found 232 contributors
Spreadsheet-ready CSV generated: contributors.csv
You can open this file directly in Apple Numbers or Microsoft Excel
```
