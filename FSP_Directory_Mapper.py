#!/usr/bin/env python3
"""
FSP Directory Mapper - Enhanced Version
A smart directory tree generator with configurable ignore patterns and user preferences
"""

import os
import sys
import subprocess
import datetime
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

# Configuration file name
CONFIG_FILE = ".fsp_directory_mapper_config.json"

# Common patterns to potentially ignore
COMMON_IGNORE_PATTERNS = {
    'directories': {
        'node_modules': 'Node.js dependencies',
        '.git': 'Git version control',
        '__pycache__': 'Python cache',
        '.pytest_cache': 'Pytest cache',
        'venv': 'Python virtual environment',
        'env': 'Python virtual environment',
        '.env': 'Environment directory',
        'dist': 'Distribution/build output',
        'build': 'Build output',
        'target': 'Build output (Java/Rust)',
        '.idea': 'IntelliJ IDEA config',
        '.vscode': 'VS Code config',
        'vendor': 'Dependencies (PHP/Go)',
        '.terraform': 'Terraform files',
        'coverage': 'Test coverage reports',
        '.nyc_output': 'NYC coverage output',
        '.next': 'Next.js build',
        '.nuxt': 'Nuxt.js build',
        'bower_components': 'Bower dependencies',
        '.sass-cache': 'Sass cache',
        'logs': 'Log files directory',
        'tmp': 'Temporary files',
        'temp': 'Temporary files',
        '.cache': 'Generic cache directory',
        'out': 'Output directory',
        '.svn': 'SVN version control',
        '.hg': 'Mercurial version control',
    },
    'files': {
        '.DS_Store': 'macOS system file',
        'Thumbs.db': 'Windows thumbnail cache',
        '.env': 'Environment variables',
        '.env.local': 'Local environment variables',
        '.env.production': 'Production environment',
        '.env.development': 'Development environment',
        '*.pyc': 'Python compiled file',
        '*.pyo': 'Python optimized file',
        '*.log': 'Log file',
        '*.tmp': 'Temporary file',
        '*.temp': 'Temporary file',
        '*.swp': 'Vim swap file',
        '*.swo': 'Vim swap file',
        '*.bak': 'Backup file',
        '*.orig': 'Original/backup file',
        '.gitignore': 'Git ignore file',
        'package-lock.json': 'NPM lock file',
        'yarn.lock': 'Yarn lock file',
        'composer.lock': 'Composer lock file',
        'Gemfile.lock': 'Ruby Bundler lock',
        'poetry.lock': 'Poetry lock file',
        'desktop.ini': 'Windows folder config',
    }
}

# Threshold for "large" directories
LARGE_DIR_THRESHOLD = 100  # Number of items

def check_and_install_dependencies():
    """Check if required packages are installed, and install them if needed."""
    required_packages = {
        'colorama': 'For colored terminal output',
        'questionary': 'For interactive prompts'
    }
    
    for package, description in required_packages.items():
        try:
            __import__(package)
        except ImportError:
            print(f"Installing required package: {package} ({description})")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"Successfully installed {package}")
            except subprocess.CalledProcessError:
                print(f"Failed to install {package}. Please install it manually with: pip install {package}")
                sys.exit(1)
    
    # Import after ensuring they're installed
    global colorama, questionary, Fore, Style
    import colorama
    import questionary
    from colorama import Fore, Style
    colorama.init()

class DirectoryMapperConfig:
    """Manages configuration and user preferences."""
    
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self.config = self.load_config()
        self.session_choices = {}
        self.new_patterns_found = set()
    
    def load_config(self) -> Dict:
        """Load configuration from file if it exists."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                print(f"{Fore.YELLOW}Warning: Could not load config file. Starting fresh.{Style.RESET_ALL}")
        return {
            'version': '1.0',
            'created': datetime.datetime.now().isoformat(),
            'ignore_patterns': {
                'directories': {},
                'files': {}
            },
            'include_large_dirs': {},
            'project_hash': None
        }
    
    def save_config(self):
        """Save configuration to file."""
        self.config['last_updated'] = datetime.datetime.now().isoformat()
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            print(f"{Fore.GREEN}Configuration saved to {self.config_file}{Style.RESET_ALL}")
        except IOError as e:
            print(f"{Fore.RED}Error saving configuration: {e}{Style.RESET_ALL}")
    
    def get_project_hash(self, base_path: str) -> str:
        """Generate a hash of the project structure for change detection."""
        hasher = hashlib.md5()
        
        # Get a sorted list of all directories and files
        all_items = []
        for root, dirs, files in os.walk(base_path):
            for d in sorted(dirs):
                all_items.append(os.path.relpath(os.path.join(root, d), base_path))
            for f in sorted(files):
                all_items.append(os.path.relpath(os.path.join(root, f), base_path))
        
        # Hash the structure
        hasher.update(''.join(sorted(all_items)).encode())
        return hasher.hexdigest()
    
    def has_project_changed(self, base_path: str) -> bool:
        """Check if the project structure has changed since last run."""
        current_hash = self.get_project_hash(base_path)
        if self.config.get('project_hash') != current_hash:
            self.config['project_hash'] = current_hash
            return True
        return False
    
    def should_ignore(self, name: str, is_dir: bool) -> Optional[bool]:
        """Check if an item should be ignored based on saved preferences."""
        category = 'directories' if is_dir else 'files'
        
        # Check exact matches
        if name in self.config['ignore_patterns'][category]:
            return self.config['ignore_patterns'][category][name]
        
        # Check pattern matches for files
        if not is_dir:
            for pattern, should_ignore in self.config['ignore_patterns']['files'].items():
                if '*' in pattern:
                    import fnmatch
                    if fnmatch.fnmatch(name, pattern):
                        return should_ignore
        
        return None

class DirectoryMapper:
    """Main directory mapping functionality."""
    
    def __init__(self, config: DirectoryMapperConfig):
        self.config = config
        self.current_script = os.path.basename(sys.argv[0])
        self.output_file = "Project_Directory.md"
        self.large_dirs_cache = {}
        self.detected_patterns = {
            'directories': set(),
            'files': set()
        }
    
    def count_directory_contents(self, path: str) -> int:
        """Count the number of items in a directory."""
        if path in self.large_dirs_cache:
            return self.large_dirs_cache[path]
        
        count = 0
        try:
            for _, dirs, files in os.walk(path):
                count += len(dirs) + len(files)
        except (PermissionError, OSError):
            count = 0
        
        self.large_dirs_cache[path] = count
        return count
    
    def is_large_directory(self, path: str) -> bool:
        """Check if a directory contains many files."""
        return self.count_directory_contents(path) > LARGE_DIR_THRESHOLD
    
    def detect_ignore_patterns(self, base_path: str):
        """Detect which ignore patterns are present in the project."""
        for root, dirs, files in os.walk(base_path):
            # Check directories
            for d in dirs:
                if d in COMMON_IGNORE_PATTERNS['directories']:
                    self.detected_patterns['directories'].add(d)
            
            # Check files
            for f in files:
                # Exact matches
                if f in COMMON_IGNORE_PATTERNS['files']:
                    self.detected_patterns['files'].add(f)
                # Pattern matches
                for pattern in COMMON_IGNORE_PATTERNS['files']:
                    if '*' in pattern:
                        import fnmatch
                        if fnmatch.fnmatch(f, pattern):
                            self.detected_patterns['files'].add(pattern)
    
    def ask_user_preferences(self, base_path: str):
        """Interactive prompt for user preferences."""
        print(f"\n{Fore.CYAN}=== Directory Mapper Configuration ==={Style.RESET_ALL}\n")
        
        # Check if we have existing configuration
        has_config = bool(self.config.config['ignore_patterns']['directories'] or 
                         self.config.config['ignore_patterns']['files'])
        
        if has_config:
            use_saved = questionary.confirm(
                "Found saved configuration. Use previous settings?",
                default=True
            ).ask()
            
            if use_saved:
                # Check for new patterns
                self.check_for_new_patterns()
                return
        
        # Ask about common ignore patterns
        print(f"\n{Fore.YELLOW}Detected common ignore patterns in your project:{Style.RESET_ALL}")
        
        # Handle directories
        if self.detected_patterns['directories']:
            print(f"\n{Fore.CYAN}Directories to potentially ignore:{Style.RESET_ALL}")
            for dir_name in sorted(self.detected_patterns['directories']):
                description = COMMON_IGNORE_PATTERNS['directories'][dir_name]
                
                # Check if it's a large directory
                example_path = None
                size_info = ""
                for root, dirs, _ in os.walk(base_path):
                    if dir_name in dirs:
                        example_path = os.path.join(root, dir_name)
                        count = self.count_directory_contents(example_path)
                        if count > LARGE_DIR_THRESHOLD:
                            size_info = f" {Fore.RED}(Contains ~{count} items!){Style.RESET_ALL}"
                        break
                
                include = questionary.confirm(
                    f"Include '{dir_name}' - {description}{size_info}?",
                    default=False
                ).ask()
                
                self.config.config['ignore_patterns']['directories'][dir_name] = not include
        
        # Handle files
        if self.detected_patterns['files']:
            print(f"\n{Fore.CYAN}File patterns to potentially ignore:{Style.RESET_ALL}")
            for file_pattern in sorted(self.detected_patterns['files']):
                description = COMMON_IGNORE_PATTERNS['files'][file_pattern]
                
                include = questionary.confirm(
                    f"Include '{file_pattern}' - {description}?",
                    default=False
                ).ask()
                
                self.config.config['ignore_patterns']['files'][file_pattern] = not include
        
        # Ask about saving preferences
        save_config = questionary.confirm(
            "\nSave these preferences for future runs?",
            default=True
        ).ask()
        
        if save_config:
            self.config.save_config()
    
    def check_for_new_patterns(self):
        """Check for new patterns that weren't in the saved configuration."""
        new_dirs = set()
        new_files = set()
        
        # Check for new directory patterns
        for dir_name in self.detected_patterns['directories']:
            if dir_name not in self.config.config['ignore_patterns']['directories']:
                new_dirs.add(dir_name)
        
        # Check for new file patterns
        for file_pattern in self.detected_patterns['files']:
            if file_pattern not in self.config.config['ignore_patterns']['files']:
                new_files.add(file_pattern)
        
        # Ask about new patterns
        if new_dirs or new_files:
            print(f"\n{Fore.YELLOW}New ignore patterns detected since last run:{Style.RESET_ALL}")
            
            if new_dirs:
                print(f"\n{Fore.CYAN}New directories:{Style.RESET_ALL}")
                for dir_name in sorted(new_dirs):
                    description = COMMON_IGNORE_PATTERNS['directories'][dir_name]
                    include = questionary.confirm(
                        f"Include '{dir_name}' - {description}?",
                        default=False
                    ).ask()
                    self.config.config['ignore_patterns']['directories'][dir_name] = not include
            
            if new_files:
                print(f"\n{Fore.CYAN}New file patterns:{Style.RESET_ALL}")
                for file_pattern in sorted(new_files):
                    description = COMMON_IGNORE_PATTERNS['files'][file_pattern]
                    include = questionary.confirm(
                        f"Include '{file_pattern}' - {description}?",
                        default=False
                    ).ask()
                    self.config.config['ignore_patterns']['files'][file_pattern] = not include
            
            # Save updated configuration
            self.config.save_config()
    
    def should_ignore_item(self, name: str, is_dir: bool, path: str = None) -> bool:
        """Determine if an item should be ignored."""
        # Always ignore the script itself and output file
        if name == self.current_script or name == self.output_file:
            return True
        
        # Check configuration
        ignore_config = self.config.should_ignore(name, is_dir)
        if ignore_config is not None:
            return ignore_config
        
        # Check file patterns
        if not is_dir:
            for pattern, should_ignore in self.config.config['ignore_patterns']['files'].items():
                if '*' in pattern:
                    import fnmatch
                    if fnmatch.fnmatch(name, pattern) and should_ignore:
                        return True
        
        return False
    
    def format_size(self, size: int) -> str:
        """Format size in a human-readable way."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0 or unit == 'TB':
                break
            size /= 1024.0
        return f"{size:.2f} {unit}"
    
    def get_file_icon(self, filename: str) -> str:
        """Get an appropriate icon for the file based on its extension."""
        icon_mapping = {
            '.py': '🐍',    # Python
            '.js': '📜',    # JavaScript
            '.html': '🌐',  # HTML
            '.css': '🎨',   # CSS
            '.json': '📋',  # JSON
            '.md': '📝',    # Markdown
            '.txt': '📄',   # Text
            '.pdf': '📑',   # PDF
            '.jpg': '🖼️',   # Image
            '.jpeg': '🖼️',  # Image
            '.png': '🖼️',   # Image
            '.gif': '🖼️',   # Image
            '.svg': '🖼️',   # Image
            '.mp3': '🎵',   # Audio
            '.mp4': '🎬',   # Video
            '.zip': '📦',   # Archive
            '.tar': '📦',   # Archive
            '.gz': '📦',    # Archive
            '.rar': '📦',   # Archive
            '.7z': '📦',    # Archive
            '.doc': '📃',   # Document
            '.docx': '📃',  # Document
            '.xls': '📊',   # Spreadsheet
            '.xlsx': '📊',  # Spreadsheet
            '.ppt': '📽️',   # Presentation
            '.pptx': '📽️',  # Presentation
            '.sh': '⚙️',    # Shell script
            '.bat': '⚙️',   # Batch script
            '.exe': '⚙️',   # Executable
            '.dll': '🔌',   # Library
            '.so': '🔌',    # Library
            '.h': '📚',     # Header
            '.c': '📚',     # C source
            '.cpp': '📚',   # C++ source
            '.java': '☕',  # Java
            '.class': '☕', # Java class
            '.rb': '💎',    # Ruby
            '.php': '🐘',   # PHP
            '.sql': '🗄️',   # SQL
            '.db': '🗄️',    # Database
            '.xml': '📰',   # XML
            '.yml': '📰',   # YAML
            '.yaml': '📰',  # YAML
            '.toml': '📰',  # TOML
            '.ini': '⚙️',   # INI configuration
            '.cfg': '⚙️',   # Configuration
            '.conf': '⚙️',  # Configuration
            '.log': '📜',   # Log
        }
        
        extension = os.path.splitext(filename)[1].lower()
        return icon_mapping.get(extension, '📄')  # Default to generic file icon
    
    def generate_directory_tree(self, start_path: str) -> List[str]:
        """Generate a nicely formatted directory tree."""
        lines = []
        start_path = os.path.abspath(start_path)
        root_name = os.path.basename(start_path)
        
        # Start with the root directory
        lines.append(f"📁 **{root_name}/**")
        
        # Store directory structure
        structure = {}
        
        # First pass: collect structure
        for root, dirs, files in os.walk(start_path):
            # Calculate relative path
            relative_path = os.path.relpath(root, start_path)
            if relative_path == '.':
                relative_path = ''
            
            # Filter directories
            filtered_dirs = []
            for d in dirs[:]:  # Use slice to allow modification during iteration
                if self.should_ignore_item(d, True, os.path.join(root, d)):
                    dirs.remove(d)  # Prevent os.walk from descending
                else:
                    filtered_dirs.append(d)
            
            # Filter files
            filtered_files = [
                f for f in files 
                if not self.should_ignore_item(f, False, os.path.join(root, f))
            ]
            
            # Store structure
            structure[relative_path] = {
                'dirs': sorted(filtered_dirs),
                'files': sorted(filtered_files)
            }
        
        # Function to recursively print the tree
        def print_tree(path: str, prefix: str = ""):
            data = structure.get(path, {'dirs': [], 'files': []})
            dirs = data['dirs']
            files = data['files']
            
            # Process all items (dirs first, then files)
            all_items = [(d, True) for d in dirs] + [(f, False) for f in files]
            
            for i, (name, is_dir) in enumerate(all_items):
                is_last = (i == len(all_items) - 1)
                
                # Determine the connector
                if is_last:
                    connector = "└── "
                    next_prefix = prefix + "    "
                else:
                    connector = "├── "
                    next_prefix = prefix + "│   "
                
                # Create the full path
                full_path = os.path.join(start_path, path, name)
                
                # Add the item
                if is_dir:
                    # Check if it's a large directory
                    item_count = self.count_directory_contents(full_path)
                    size_indicator = ""
                    if item_count > LARGE_DIR_THRESHOLD:
                        size_indicator = f" {Fore.YELLOW}({item_count} items){Style.RESET_ALL}"
                    
                    lines.append(f"{prefix}{connector}📁 **{name}/**{size_indicator}")
                    
                    # Recursively process
                    new_path = os.path.join(path, name) if path else name
                    print_tree(new_path, next_prefix)
                else:
                    # Get file information
                    try:
                        stats = os.stat(full_path)
                        size = self.format_size(stats.st_size)
                        modified = datetime.datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Format filename
                        name_without_ext, ext = os.path.splitext(name)
                        if ext:
                            formatted_name = f"{name_without_ext}`{ext}`"
                        else:
                            formatted_name = name
                        
                        # Get icon
                        icon = self.get_file_icon(name)
                        
                        lines.append(f"{prefix}{connector}{icon} {formatted_name} ({size}, {modified})")
                    except (FileNotFoundError, PermissionError):
                        lines.append(f"{prefix}{connector}📄 {name} (unavailable)")
        
        # Start recursive printing
        print_tree('')
        
        return lines
    
    def generate_statistics(self, base_path: str) -> Dict:
        """Generate statistics about the directory."""
        stats = {
            'file_count': 0,
            'dir_count': 0,
            'total_size': 0,
            'ignored_items': 0,
            'file_types': {}
        }
        
        for root, dirs, files in os.walk(base_path):
            # Count directories
            for d in dirs[:]:
                if self.should_ignore_item(d, True, os.path.join(root, d)):
                    dirs.remove(d)
                    stats['ignored_items'] += 1
                else:
                    stats['dir_count'] += 1
            
            # Count files
            for f in files:
                if self.should_ignore_item(f, False, os.path.join(root, f)):
                    stats['ignored_items'] += 1
                else:
                    stats['file_count'] += 1
                    
                    # File size
                    try:
                        stats['total_size'] += os.path.getsize(os.path.join(root, f))
                    except (FileNotFoundError, PermissionError):
                        pass
                    
                    # File types
                    ext = os.path.splitext(f)[1].lower()
                    if ext:
                        stats['file_types'][ext] = stats['file_types'].get(ext, 0) + 1
        
        return stats
    
    def generate_directory_markdown(self):
        """Generate a markdown file with the directory structure."""
        current_dir = os.getcwd()
        parent_dir_name = os.path.basename(current_dir)
        
        print(f"\n{Fore.CYAN}Scanning directory structure...{Style.RESET_ALL}")
        
        # Detect patterns first
        self.detect_ignore_patterns(current_dir)
        
        # Ask user preferences
        self.ask_user_preferences(current_dir)
        
        print(f"\n{Fore.CYAN}Generating directory tree...{Style.RESET_ALL}")
        
        # Generate content
        content = f"# Project Directory: {parent_dir_name}\n\n"
        content += f"Directory structure generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Add statistics
        stats = self.generate_statistics(current_dir)
        content += f"* Total files: {stats['file_count']}\n"
        content += f"* Total directories: {stats['dir_count']}\n"
        content += f"* Total size: {self.format_size(stats['total_size'])}\n"
        if stats['ignored_items'] > 0:
            content += f"* Ignored items: {stats['ignored_items']}\n"
        content += "\n"
        
        # Add tree structure
        content += "```\n"
        tree = self.generate_directory_tree(current_dir)
        content += "\n".join(tree)
        content += "\n```\n\n"
        
        # Add file type summary
        if stats['file_types']:
            content += "## File Type Summary\n\n"
            sorted_types = sorted(stats['file_types'].items(), key=lambda x: x[1], reverse=True)
            for ext, count in sorted_types[:10]:  # Top 10 file types
                content += f"* `{ext}`: {count} files\n"
            if len(sorted_types) > 10:
                content += f"* ... and {len(sorted_types) - 10} more file types\n"
            content += "\n"
        
        # Add icon legend
        content += "## Icon Legend\n\n"
        content += "📁 - Directory\n"
        
        # Group icons by type
        icon_groups = {}
        icon_mapping = {
            '.py': '🐍', '.js': '📜', '.html': '🌐', '.css': '🎨',
            '.json': '📋', '.md': '📝', '.txt': '📄', '.pdf': '📑',
            '.jpg': '🖼️', '.jpeg': '🖼️', '.png': '🖼️', '.gif': '🖼️',
            '.svg': '🖼️', '.mp3': '🎵', '.mp4': '🎬', '.zip': '📦',
            '.tar': '📦', '.gz': '📦', '.rar': '📦', '.7z': '📦',
            '.doc': '📃', '.docx': '📃', '.xls': '📊', '.xlsx': '📊',
            '.ppt': '📽️', '.pptx': '📽️', '.sh': '⚙️', '.bat': '⚙️',
            '.exe': '⚙️', '.dll': '🔌', '.so': '🔌', '.h': '📚',
            '.c': '📚', '.cpp': '📚', '.java': '☕', '.class': '☕',
            '.rb': '💎', '.php': '🐘', '.sql': '🗄️', '.db': '🗄️',
            '.xml': '📰', '.yml': '📰', '.yaml': '📰', '.toml': '📰',
            '.ini': '⚙️', '.cfg': '⚙️', '.conf': '⚙️', '.log': '📜',
        }
        
        for ext, icon in icon_mapping.items():
            if icon not in icon_groups:
                icon_groups[icon] = []
            icon_groups[icon].append(ext)
        
        for icon, extensions in sorted(icon_groups.items()):
            exts = sorted(extensions)
            if len(exts) > 5:
                ext_display = ", ".join(exts[:5]) + ", etc."
            else:
                ext_display = ", ".join(exts)
            content += f"{icon} - {ext_display}\n"
        
        # Write the file
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n{Fore.GREEN}✓ Directory structure has been written to {self.output_file}{Style.RESET_ALL}")
        
        # Show configuration status
        if self.config.config['ignore_patterns']['directories'] or self.config.config['ignore_patterns']['files']:
            ignored_count = sum(1 for v in self.config.config['ignore_patterns']['directories'].values() if v)
            ignored_count += sum(1 for v in self.config.config['ignore_patterns']['files'].values() if v)
            print(f"{Fore.CYAN}ℹ Configuration: {ignored_count} patterns ignored{Style.RESET_ALL}")
            print(f"{Fore.CYAN}ℹ Config file: {self.config.config_file}{Style.RESET_ALL}")

def main():
    """Main function to run the script."""
    try:
        # Check and install dependencies
        check_and_install_dependencies()
        
        # Initialize configuration
        config = DirectoryMapperConfig()
        
        # Create mapper and generate
        mapper = DirectoryMapper(config)
        mapper.generate_directory_markdown()
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Operation cancelled by user.{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Fore.RED}Error: {e}{Style.RESET_ALL}")
        sys.exit(1)

if __name__ == "__main__":
    main()