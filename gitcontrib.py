#!/usr/bin/env python3
"""
Git Contributor Analysis Tool
Analyzes git repositories and generates contributor reports with configurable filters.
"""

import argparse
import csv
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import quote_plus, urlparse
import hashlib
import re

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class Contributor:
    """Represents a contributor with their statistics."""
    name: str
    email: str
    commit_count: int
    first_commit: datetime
    last_commit: datetime
    lines_added: int
    lines_deleted: int


@dataclass
class AnalysisOptions:
    """Configuration options for analysis."""
    repo: Optional[str] = None
    subdir: Optional[str] = None
    branch: str = "HEAD"
    since: Optional[str] = None
    until: Optional[str] = None
    output: str = "contributors.csv"
    cache_dir: Optional[str] = None
    linkedin: bool = True
    format: str = "numbers"
    include_line_stats: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisOptions':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


class OptionsCache:
    """Manages caching of options in the current directory."""
    
    CACHE_FILE = ".git-contributor-options.json"
    
    @classmethod
    def save(cls, options: AnalysisOptions):
        """Save options to cache file in current directory."""
        cache_path = Path.cwd() / cls.CACHE_FILE
        try:
            with open(cache_path, 'w') as f:
                json.dump(options.to_dict(), f, indent=2)
            logger.info(f"Options saved to {cache_path}")
        except Exception as e:
            logger.warning(f"Could not save options cache: {e}")
    
    @classmethod
    def load(cls) -> Optional[AnalysisOptions]:
        """Load options from cache file in current directory."""
        cache_path = Path.cwd() / cls.CACHE_FILE
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded options from {cache_path}")
            return AnalysisOptions.from_dict(data)
        except Exception as e:
            logger.warning(f"Could not load options cache: {e}")
            return None
    
    @classmethod
    def exists(cls) -> bool:
        """Check if cache file exists."""
        return (Path.cwd() / cls.CACHE_FILE).exists()


class GitHubURLParser:
    """Parses and normalizes GitHub URLs."""
    
    @staticmethod
    def parse_github_url(url: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Parse a GitHub URL and extract clone URL, branch, and subdirectory.
        
        Returns:
            Tuple of (clone_url, branch, subdir)
        
        Examples:
            https://github.com/llvm/llvm-project/tree/main -> 
                (https://github.com/llvm/llvm-project.git, main, None)
            
            https://github.com/llvm/llvm-project/tree/main/clang ->
                (https://github.com/llvm/llvm-project.git, main, clang)
            
            https://github.com/llvm/llvm-project ->
                (https://github.com/llvm/llvm-project.git, None, None)
        """
        # Remove trailing # and whitespace
        url = url.rstrip('#').strip()
        
        # Parse the URL
        parsed = urlparse(url)
        
        # Check if it's a GitHub URL
        if 'github.com' not in parsed.netloc:
            # Not a GitHub URL, return as-is
            return url, None, None
        
        # Split the path
        path_parts = [p for p in parsed.path.split('/') if p]
        
        if len(path_parts) < 2:
            # Invalid GitHub URL
            return url, None, None
        
        owner = path_parts[0]
        repo = path_parts[1]
        
        branch = None
        subdir = None
        
        # Check if URL contains /tree/ or /blob/
        if len(path_parts) >= 4 and path_parts[2] in ['tree', 'blob']:
            branch = path_parts[3]
            
            # Everything after the branch is the subdirectory
            if len(path_parts) > 4:
                subdir = '/'.join(path_parts[4:])
        
        # Construct the clone URL
        # Remove .git from repo name if already present to avoid .git.git
        if repo.endswith('.git'):
            clone_url = f"https://github.com/{owner}/{repo}"
        else:
            clone_url = f"https://github.com/{owner}/{repo}.git"
        
        return clone_url, branch, subdir
    
    @staticmethod
    def normalize_git_url(url: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Normalize any git URL for cloning.
        
        Returns:
            Tuple of (clone_url, branch, subdir)
        """
        # Try GitHub-specific parsing first
        if 'github.com' in url:
            return GitHubURLParser.parse_github_url(url)
        
        # For other URLs, just return as-is
        return url, None, None


class GitAnalyzer:
    """Handles git repository operations and analysis."""
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_repo_cache_path(self, repo_url: str, subdir: Optional[str] = None) -> Path:
        """Generate a unique cache directory name for a repository."""
        # Create a hash of the repo URL for the directory name
        repo_hash = hashlib.md5(repo_url.encode()).hexdigest()[:12]
        # Extract repo name from URL
        repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
        cache_path = self.cache_dir / f"{repo_name}_{repo_hash}"
        
        if subdir:
            cache_path = cache_path / subdir
        
        return cache_path
    
    def _run_git_command(self, cmd: List[str], cwd: Path) -> str:
        """Execute a git command and return output."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running git command: {e}")
            logger.error(f"stderr: {e.stderr}")
            raise
    
    def clone_or_update_repo(self, repo_url: str) -> Path:
        """Clone repository if not cached, otherwise update it."""
        cache_path = self._get_repo_cache_path(repo_url)

        if cache_path.exists():
            logger.info(f"Updating cached repository at {cache_path}...")
            try:
                self._run_git_command(['git', 'fetch', '--all'], cache_path)
                self._run_git_command(['git', 'pull', '--all'], cache_path)
            except subprocess.CalledProcessError:
                logger.warning("Update failed, repository may be corrupted. Re-cloning...")
                import shutil
                shutil.rmtree(cache_path)
                return self.clone_or_update_repo(repo_url)
        else:
            logger.info(f"Cloning repository to {cache_path}...")
            self._run_git_command(['git', 'clone', repo_url, str(cache_path)], self.cache_dir)

        return cache_path
    
    def analyze_contributors(
        self,
        repo_path: Path,
        subdir: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        branch: str = "HEAD",
        include_line_stats: bool = False
    ) -> List[Contributor]:
        """Analyze contributors in a repository."""

        # Build git log command
        cmd = ['git', 'log', branch, '--no-merges', '--format=%H|%an|%ae|%at']

        if since:
            cmd.append(f'--since={since}')
        if until:
            cmd.append(f'--until={until}')
        if subdir:
            cmd.append('--')
            cmd.append(subdir)

        logger.info(f"Analyzing commits with command: {' '.join(cmd)}")
        log_output = self._run_git_command(cmd, repo_path)

        # Count total commits for progress indication
        commit_lines = [line for line in log_output.strip().split('\n') if line]
        total_commits = len(commit_lines)
        logger.info(f"Found {total_commits} commits to analyze")

        # Parse commits
        contributors_data: Dict[str, Dict] = {}

        for idx, line in enumerate(commit_lines, 1):
            commit_hash, name, email, timestamp = line.split('|')
            commit_date = datetime.fromtimestamp(int(timestamp))

            key = (name, email)
            if key not in contributors_data:
                contributors_data[key] = {
                    'name': name,
                    'email': email,
                    'commits': [],
                    'lines_added': 0,
                    'lines_deleted': 0
                }

            contributors_data[key]['commits'].append(commit_date)

            # Show progress every 100 commits or at the end
            if idx % 100 == 0 or idx == total_commits:
                percentage = idx * 100 // total_commits
                # For progress updates, we need to handle carriage return for inline updates
                # This works in terminal, GUI will need to handle it
                msg = f"  Processed {idx}/{total_commits} commits ({percentage}%)"
                if idx < total_commits:
                    # Inline update - print to stdout with \r
                    sys.stdout.write(f"\r{msg}")
                    sys.stdout.flush()
                else:
                    # Final update - use logger
                    sys.stdout.write(f"\r{msg}\n")
                    sys.stdout.flush()

        total_contributors = len(contributors_data)

        # Get line statistics for each contributor (optional)
        if include_line_stats:
            logger.info(f"Gathering line statistics for {total_contributors} contributors...")

            for idx, ((name, email), data) in enumerate(contributors_data.items(), 1):
                stats_cmd = ['git', 'log', branch, '--no-merges', '--numstat',
                            f'--author={email}', '--format=']

                if since:
                    stats_cmd.append(f'--since={since}')
                if until:
                    stats_cmd.append(f'--until={until}')
                if subdir:
                    stats_cmd.append('--')
                    stats_cmd.append(subdir)

                stats_output = self._run_git_command(stats_cmd, repo_path)

                for line in stats_output.strip().split('\n'):
                    if not line:
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                        data['lines_added'] += int(parts[0])
                        data['lines_deleted'] += int(parts[1])

                # Show progress for contributors
                is_last = idx == total_contributors
                msg = f"  [{idx}/{total_contributors}] {name} ({len(data['commits'])} commits)"
                if is_last:
                    sys.stdout.write(f"\r{msg}\n")
                    sys.stdout.flush()
                else:
                    sys.stdout.write(f"\r{msg}")
                    sys.stdout.flush()

            if total_contributors > 0:
                # Final newline already added above
                pass
        else:
            logger.info(f"Found {total_contributors} unique contributors (line statistics skipped)")

        
        # Convert to Contributor objects
        contributors = []
        for data in contributors_data.values():
            if data['commits']:
                contributors.append(Contributor(
                    name=data['name'],
                    email=data['email'],
                    commit_count=len(data['commits']),
                    first_commit=min(data['commits']),
                    last_commit=max(data['commits']),
                    lines_added=data['lines_added'],
                    lines_deleted=data['lines_deleted']
                ))
        
        # Sort by commit count (descending)
        contributors.sort(key=lambda c: c.commit_count, reverse=True)
        
        return contributors


class ReportGenerator:
    """Generates reports in various formats."""
    
    @staticmethod
    def generate_linkedin_search_url(name: str, email: str) -> str:
        """Generate a LinkedIn search URL for a contributor."""
        # Extract company from email domain if possible
        domain = email.split('@')[-1]
        # company = domain.split('.')[0] if '.' in domain else domain
        
        # Create search query
        query = f"{name}"
        encoded_query = quote_plus(query)
        
        return f"https://www.linkedin.com/search/results/people/?keywords={encoded_query}"
    
    def generate_csv(
        self,
        contributors: List[Contributor],
        output_file: Path,
        include_linkedin: bool = True
    ):
        """Generate a CSV report."""
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'Name', 'Email', 'Commits', 'Lines Added', 'Lines Deleted',
                'First Commit', 'Last Commit'
            ]
            if include_linkedin:
                fieldnames.append('LinkedIn Search')
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for contributor in contributors:
                row = {
                    'Name': contributor.name,
                    'Email': contributor.email,
                    'Commits': contributor.commit_count,
                    'Lines Added': contributor.lines_added,
                    'Lines Deleted': contributor.lines_deleted,
                    'First Commit': contributor.first_commit.strftime('%Y-%m-%d'),
                    'Last Commit': contributor.last_commit.strftime('%Y-%m-%d')
                }
                
                if include_linkedin:
                    row['LinkedIn Search'] = self.generate_linkedin_search_url(
                        contributor.name, contributor.email
                    )
                
                writer.writerow(row)

        logger.info(f"CSV report generated: {output_file}")
    
    def generate_numbers_csv(
        self,
        contributors: List[Contributor],
        output_file: Path,
        include_linkedin: bool = True
    ):
        """Generate a CSV optimized for Apple Numbers/Excel."""
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'Name', 'Email', 'Commits', 'Lines Added', 'Lines Deleted',
                'First Commit', 'Last Commit'
            ]
            if include_linkedin:
                fieldnames.append('LinkedIn Search')
            
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=',')
            writer.writeheader()
            
            for contributor in contributors:
                row = {
                    'Name': contributor.name,
                    'Email': contributor.email,
                    'Commits': contributor.commit_count,
                    'Lines Added': contributor.lines_added,
                    'Lines Deleted': contributor.lines_deleted,
                    'First Commit': contributor.first_commit.strftime('%Y-%m-%d'),
                    'Last Commit': contributor.last_commit.strftime('%Y-%m-%d')
                }
                
                if include_linkedin:
                    row['LinkedIn Search'] = self.generate_linkedin_search_url(
                        contributor.name, contributor.email
                    )
                
                writer.writerow(row)

        logger.info(f"Spreadsheet-ready CSV generated: {output_file}")
        logger.info(f"You can open this file directly in Apple Numbers or Microsoft Excel")


def get_default_cache_dir() -> Path:
    """Get the default cache directory following XDG Base Directory specification."""
    # Check XDG_CACHE_HOME first (standard on Linux)
    xdg_cache = os.environ.get('XDG_CACHE_HOME')
    if xdg_cache:
        return Path(xdg_cache) / 'git-contributor-analyzer'
    
    # Fall back to ~/.local/share for persistent data (more appropriate than cache)
    # since we want to keep repos across sessions
    xdg_data = os.environ.get('XDG_DATA_HOME')
    if xdg_data:
        return Path(xdg_data) / 'git-contributor-analyzer'
    
    # Default: ~/.local/share/git-contributor-analyzer
    return Path.home() / '.local' / 'share' / 'git-contributor-analyzer'


def interactive_mode(options: AnalysisOptions) -> AnalysisOptions:
    """Run interactive mode to configure options."""
    print("\n" + "="*60)
    print("Git Contributor Analysis - Interactive Mode")
    print("="*60)

    if OptionsCache.exists():
        print(f"\n(Options loaded from {OptionsCache.CACHE_FILE})")

    while True:
        print("\nCurrent Configuration:")
        print(f"  1. Repository URL: {options.repo or '(not set)'}")
        print(f"  2. Subdirectory: {options.subdir or '(none)'}")
        print(f"  3. Branch: {options.branch}")
        print(f"  4. Since date: {options.since or '(all time)'}")
        print(f"  5. Until date: {options.until or '(now)'}")
        print(f"  6. Output file: {options.output}")
        print(f"  7. Output format: {options.format}")
        print(f"  8. Include LinkedIn: {options.linkedin}")
        print(f"  9. Include line statistics: {options.include_line_stats}")
        print(f" 10. Cache directory: {options.cache_dir}")
        print("\n  r. Run Analysis")
        print("  s. Save options and exit")
        print("  0. Exit without saving")

        choice = input("\nSelect option (0-10, r, s): ").strip().lower()
        
        if choice == '0':
            print("Exiting without saving...")
            sys.exit(0)
        elif choice == 's':
            OptionsCache.save(options)
        elif choice == '1':
            url = input("Enter repository URL: ").strip()
            # Parse and normalize the URL
            clone_url, branch, subdir = GitHubURLParser.normalize_git_url(url)
            options.repo = clone_url
            
            # Auto-fill branch and subdir if detected
            if branch and not options.branch:
                print(f"  → Detected branch: {branch}")
                options.branch = branch
            if subdir:
                print(f"  → Detected subdirectory: {subdir}")
                if options.subdir:
                    print(f"  → Merging with existing subdir: {options.subdir}/{subdir}")
                    options.subdir = f"{options.subdir}/{subdir}"
                else:
                    options.subdir = subdir
            
            if clone_url != url:
                print(f"  → Normalized to: {clone_url}")
        elif choice == '2':
            subdir = input("Enter subdirectory (leave empty for none): ").strip()
            options.subdir = subdir if subdir else None
        elif choice == '3':
            options.branch = input("Enter branch name [HEAD]: ").strip() or "HEAD"
        elif choice == '4':
            since = input("Enter start date (YYYY-MM-DD or leave empty): ").strip()
            options.since = since if since else None
        elif choice == '5':
            until = input("Enter end date (YYYY-MM-DD or leave empty): ").strip()
            options.until = until if until else None
        elif choice == '6':
            options.output = input("Enter output file path: ").strip()
        elif choice == '7':
            fmt = input("Enter format (csv/numbers) [numbers]: ").strip().lower()
            options.format = fmt if fmt in ['csv', 'numbers'] else 'numbers'
        elif choice == '8':
            linkedin = input("Include LinkedIn search URLs? (y/n) [y]: ").strip().lower()
            options.linkedin = linkedin != 'n'
        elif choice == '9':
            line_stats = input("Include line statistics? (y/n) [n]: ").strip().lower()
            options.include_line_stats = line_stats == 'y'
        elif choice == '10':
            options.cache_dir = input("Enter cache directory path: ").strip()
        elif choice == 'r':
            if not options.repo:
                print("\nError: Repository URL is required!")
                continue
            # Save options before running
            OptionsCache.save(options)
            return options
        else:
            print("Invalid option!")
    
    return options


def setup_logging(level=logging.INFO):
    """Configure logging for the application."""
    # Create handler that outputs to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)

    # Configure root logger
    logger.setLevel(level)
    logger.addHandler(handler)

    # Prevent duplicate log messages
    logger.propagate = False


def main():
    # Set up logging first
    setup_logging()

    parser = argparse.ArgumentParser(
        description='Analyze git repository contributors and generate reports',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (default)
  %(prog)s
  
  # Non-interactive mode with GitHub URL
  %(prog)s --no-interactive https://github.com/llvm/llvm-project/tree/main
  
  # GitHub URL with subdirectory
  %(prog)s --no-interactive https://github.com/llvm/llvm-project/tree/main/clang
  
  # Analyze with date range
  %(prog)s --no-interactive https://github.com/user/repo --since 2024-01-01 --until 2024-12-31
  
  # Specific branch
  %(prog)s --no-interactive https://github.com/user/repo --branch develop

Note: GitHub URLs are automatically normalized for git clone.
      URLs like https://github.com/owner/repo/tree/branch/subdir are parsed to extract
      the clone URL, branch, and subdirectory automatically.

      Options are cached in .git-contributor-options.json in the current directory
      when using interactive mode.
        """
    )
    
    parser.add_argument('repo', nargs='?', help='Git repository URL (GitHub URLs with /tree/ are automatically parsed)')
    parser.add_argument('-s', '--subdir', help='Analyze only a subdirectory')
    parser.add_argument('-b', '--branch', help='Branch to analyze (default: HEAD)')
    parser.add_argument('--since', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--until', help='End date (YYYY-MM-DD)')
    parser.add_argument('-o', '--output', help='Output file path (default: contributors.csv)')
    parser.add_argument('--cache-dir',
                       help='Cache directory for cloned repositories (default: ~/.local/share/git-contributor-analyzer)')
    parser.add_argument('--no-linkedin', dest='linkedin', action='store_false',
                       help='Exclude LinkedIn search URLs from output')
    parser.add_argument('--line-stats', dest='include_line_stats', action='store_true',
                       help='Include line statistics (lines added/deleted) - slower but more detailed')
    parser.add_argument('--no-interactive', dest='interactive', action='store_false', default=True,
                       help='Disable interactive mode (run directly with command-line args)')
    parser.add_argument('--format', choices=['csv', 'numbers'],
                       help='Output format (default: numbers)')
    
    args = parser.parse_args()
    
    # Normalize the repo URL if provided
    if args.repo:
        clone_url, detected_branch, detected_subdir = GitHubURLParser.normalize_git_url(args.repo)
        args.repo = clone_url

        # Use detected branch/subdir if not explicitly provided
        if detected_branch and not args.branch:
            args.branch = detected_branch
            logger.info(f"Detected branch from URL: {detected_branch}")

        if detected_subdir:
            if args.subdir:
                # Merge subdirs
                args.subdir = f"{args.subdir}/{detected_subdir}"
            else:
                args.subdir = detected_subdir
            logger.info(f"Detected subdirectory from URL: {detected_subdir}")
    
    # Determine if we should use interactive mode
    use_interactive = args.interactive
    
    # If no repo provided and not in non-interactive mode, force interactive
    if not args.repo and not use_interactive:
        parser.error("Repository URL is required in non-interactive mode")
    
    # Load or create options
    if use_interactive:
        # Try to load cached options
        cached_options = OptionsCache.load()
        if cached_options:
            options = cached_options
        else:
            options = AnalysisOptions()
            # Set default cache dir
            options.cache_dir = str(get_default_cache_dir())
        
        # Override with any command-line arguments provided
        if args.repo:
            options.repo = args.repo
        if args.subdir:
            options.subdir = args.subdir
        if args.branch:
            options.branch = args.branch
        if args.since:
            options.since = args.since
        if args.until:
            options.until = args.until
        if args.output:
            options.output = args.output
        if args.cache_dir:
            options.cache_dir = args.cache_dir
        if not args.linkedin:
            options.linkedin = False
        if args.include_line_stats:
            options.include_line_stats = True
        if args.format:
            options.format = args.format
        
        # Run interactive mode
        options = interactive_mode(options)
    else:
        # Non-interactive mode: use command-line args only
        options = AnalysisOptions(
            repo=args.repo,
            subdir=args.subdir,
            branch=args.branch or "HEAD",
            since=args.since,
            until=args.until,
            output=args.output or "contributors.csv",
            cache_dir=args.cache_dir or str(get_default_cache_dir()),
            linkedin=args.linkedin,
            format=args.format or "numbers",
            include_line_stats=args.include_line_stats
        )
    
    if not options.repo:
        parser.error("Repository URL is required")
    
    # Initialize
    cache_dir = Path(options.cache_dir)
    analyzer = GitAnalyzer(cache_dir)
    report_gen = ReportGenerator()
    
    try:
        # Clone/update repository
        repo_path = analyzer.clone_or_update_repo(options.repo)

        # Analyze contributors
        logger.info("Analyzing contributors...")
        contributors = analyzer.analyze_contributors(
            repo_path=repo_path,
            subdir=options.subdir,
            since=options.since,
            until=options.until,
            branch=options.branch,
            include_line_stats=options.include_line_stats
        )

        if not contributors:
            logger.warning("No contributors found matching the criteria.")
            return

        logger.info(f"Found {len(contributors)} contributors")

        # Generate report
        output_path = Path(options.output)

        if options.format == 'numbers':
            report_gen.generate_numbers_csv(contributors, output_path, options.linkedin)
        else:
            report_gen.generate_csv(contributors, output_path, options.linkedin)

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

