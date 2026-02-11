# Git Contributor Analyzer

A tool for analyzing Git repository contributors and generating recruitment-ready reports. Perfect for identifying and reaching out to open-source contributors for recruiting purposes.

WARNING: Code generated 99% with Claude. Read at your own risks.

## Quick Start

Get started in minutes:

```bash
# Clone the repository
git clone https://github.com/arames/git_recruiting.git
cd git_recruiting

# Run the interactive tool
./gitcontrib.py
```

**Example Session:**

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

**Opening the Results:**

After the analysis completes, open the CSV file:

```bash
open contributors.csv
```

Or navigate to the `git_recruiting` directory in Finder and double-click `contributors.csv` to open it in Numbers or Excel.

**Tip:** To open Terminal in a specific folder from Finder, right-click the folder while holding the **Option** key, then select **"Open Terminal at Folder"** (or go to **Services → New Terminal at Folder**).

## Features

- Analyze any Git repository (local or remote)
- Filter contributors by date range, subdirectory, and branch
- Generate spreadsheet-ready CSV reports (Excel/Numbers compatible)
- Automatic LinkedIn search URL generation for each contributor
- Smart caching to speed up repeated analyses
- Interactive mode with saved preferences
- Support for GitHub URL parsing (handles /tree/, /blob/ paths)

## Installation

### Requirements

- Python 3.7 or higher
- Git installed and available in PATH

### GitHub Setup (Optional)

The tool works with public GitHub repositories without any setup. For private repositories or to avoid rate limits, you'll need to authenticate with GitHub.

**Option 1: HTTPS with Personal Access Token (Recommended for most users)**

1. Create a Personal Access Token (PAT) on GitHub:
   - Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Click "Generate new token (classic)"
   - Give it a name (e.g., "Git Contributor Analyzer")
   - Select scope: `repo` (for private repos) or just `public_repo` (for public repos only)
   - Click "Generate token" and copy it

2. Configure Git to use your token:
   ```bash
   git config --global credential.helper store
   ```

3. The first time you clone, Git will prompt for credentials:
   - Username: your GitHub username
   - Password: paste your Personal Access Token (not your GitHub password!)

   Git will remember this for future use.

**Option 2: SSH Keys (For advanced users)**

1. Generate an SSH key (if you don't have one):
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   ```

2. Add your SSH key to GitHub:
   - Copy your public key: `cat ~/.ssh/id_ed25519.pub`
   - Go to GitHub Settings → SSH and GPG keys → New SSH key
   - Paste the key and save

3. Use SSH URLs instead of HTTPS:
   ```bash
   ./gitcontrib.py git@github.com:owner/repo.git
   ```

**Troubleshooting Authentication:**
- If you get "Authentication failed": Your token may be expired or lack the required permissions
- If you get "Permission denied (publickey)": Your SSH key isn't properly set up
- For organization repositories: Ensure your token has access to the organization

## Usage

### Interactive Mode (Recommended)

Run the tool without arguments for an interactive menu:

```bash
./gitcontrib.py
```

The tool will save your preferences and reload them next time.

### Command-Line Mode

```bash
./gitcontrib.py <repo-url> [options]
```

**Options:**
- `--branch BRANCH` - Branch to analyze (default: HEAD)
- `--subdir PATH` - Analyze only a specific subdirectory
- `--since YYYY-MM-DD` - Only include commits after this date
- `--until YYYY-MM-DD` - Only include commits before this date
- `--output FILE` - Output CSV filename (default: contributors.csv)
- `--format {csv,numbers}` - Output format (default: numbers)
- `--no-linkedin` - Exclude LinkedIn search URLs
- `--cache-dir PATH` - Custom cache directory

**Examples:**

```bash
# Analyze all contributors to LLVM's MLIR subdirectory since 2024
./gitcontrib.py https://github.com/llvm/llvm-project.git \
  --subdir mlir \
  --since 2024-01-01

# Analyze a specific GitHub subdirectory (auto-detects path)
./gitcontrib.py https://github.com/llvm/llvm-project/tree/main/mlir

# Analyze a local repository
./gitcontrib.py /path/to/local/repo --since 2024-01-01
```

## Output Format

The tool generates a CSV file with the following columns:

- **Name** - Contributor's name from Git commits
- **Email** - Contributor's email address
- **Commits** - Number of commits in the analyzed period/directory
- **LinkedIn** - LinkedIn search URL (if enabled)

The default "numbers" format uses semicolons and special formatting optimized for Apple Numbers and Excel. Use `--format csv` for standard CSV format.

## Configuration

Settings are automatically saved to `.git-contributor-options.json` in your current directory or home directory. This includes:
- Repository URL
- Branch, subdirectory, date filters
- Output preferences
- Cache directory location

## Tips

- Use subdirectory filtering to focus on specific components (e.g., a particular service or module)
- Date ranges help find recent active contributors vs. historical ones
- LinkedIn URLs make it easy to research candidates
- The cache directory speeds up repeated analyses - it's safe to reuse

## Troubleshooting

**"Repository not found"**: Ensure the Git URL is correct and accessible

**"No contributors found"**: Check your filters (date range, subdirectory, branch)

**Slow performance**: First run clones the repo - subsequent runs use the cache

## License

MIT License - see the code for details.
