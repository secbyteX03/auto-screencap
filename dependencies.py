"""
Dependency management and checking for auto-screencap.
"""
import sys
import subprocess
import importlib.metadata
import logging
from typing import Dict, List, Tuple, Optional, Set

logger = logging.getLogger("auto-screencap.dependencies")

# Define core and optional dependencies
CORE_DEPENDENCIES = {
    'Pillow': 'Pillow>=9.0.0',
    'pyautogui': 'pyautogui>=0.9.53',
    'pygetwindow': 'pygetwindow>=0.0.9',
}

OPTIONAL_DEPENDENCIES = {
    'opencv-python': {
        'package': 'opencv-python>=4.5.5.64',
        'purpose': 'Face blurring functionality',
    },
    'pystray': {
        'package': 'pystray>=0.19.2',
        'purpose': 'System tray icon',
    },
    'plyer': {
        'package': 'plyer>=2.1.0',
        'purpose': 'Desktop notifications',
    },
}

# Define test dependencies
TEST_DEPENDENCIES = {
    'pytest': 'pytest>=7.0.0',
    'pytest-mock': 'pytest-mock>=3.10.0',
}

class DependencyManager:
    """Manages and checks dependencies for the application."""
    
    def __init__(self):
        """Initialize the dependency manager."""
        self.installed_packages = self._get_installed_packages()
        self.missing_core: List[Tuple[str, str]] = []
        self.missing_optional: List[Tuple[str, str, str]] = []
        
    def check_dependencies(self) -> bool:
        """Check if all required dependencies are installed.
        
        Returns:
            bool: True if all core dependencies are installed, False otherwise
        """
        self.missing_core = []
        self.missing_optional = []
        
        # Check core dependencies
        for name, version_spec in CORE_DEPENDENCIES.items():
            if not self._is_installed(name, version_spec):
                self.missing_core.append((name, version_spec))
        
        # Check optional dependencies
        for name, dep_info in OPTIONAL_DEPENDENCIES.items():
            if not self._is_installed(name, dep_info['package'].split('>=')[1]):
                self.missing_optional.append((name, dep_info['package'], dep_info['purpose']))
        
        return len(self.missing_core) == 0
    
    def install_missing_dependencies(self, optional: bool = False) -> bool:
        """Install missing dependencies.
        
        Args:
            optional: Whether to also install optional dependencies
            
        Returns:
            bool: True if installation was successful, False otherwise
        """
        if not self.missing_core and (not optional or not self.missing_optional):
            return True
            
        try:
            # Install core dependencies
            if self.missing_core:
                packages = [f"{name}{version}" for name, version in self.missing_core]
                self._install_packages(packages)
                
            # Install optional dependencies if requested
            if optional and self.missing_optional:
                packages = [f"{name}{version}" for name, version, _ in self.missing_optional]
                self._install_packages(packages)
                
            # Update installed packages cache
            self.installed_packages = self._get_installed_packages()
            
            # Verify all dependencies are now installed
            return self.check_dependencies()
            
        except Exception as e:
            logger.error(f"Failed to install dependencies: {e}")
            return False
    
    def get_install_commands(self) -> str:
        """Get the commands needed to install missing dependencies.
        
        Returns:
            str: Commands to run in the terminal
        """
        commands = []
        
        if self.missing_core:
            core_pkgs = [f"{name}{version}" for name, version in self.missing_core]
            commands.append(f"pip install {' '.join(core_pkgs)}")
        
        if self.missing_optional:
            optional_pkgs = [f"{name}{version}" for name, version, _ in self.missing_optional]
            commands.append(f"# Optional features:\npip install {' '.join(optional_pkgs)}")
        
        return "\n".join(commands)
    
    def print_status(self) -> None:
        """Print the status of dependencies to the console."""
        if not self.missing_core and not self.missing_optional:
            print("✓ All dependencies are installed.")
            return
        
        if self.missing_core:
            print("\nMissing core dependencies:")
            for name, version in self.missing_core:
                print(f"  - {name}{version} (required)")
        
        if self.missing_optional:
            print("\nMissing optional dependencies (features will be disabled):")
            for name, version, purpose in self.missing_optional:
                print(f"  - {name}{version} ({purpose})")
        
        print("\nTo install missing dependencies, run:")
        print(self.get_install_commands())
    
    def _is_installed(self, package_name: str, version_spec: str = None) -> bool:
        """Check if a package is installed with the specified version.
        
        Args:
            package_name: Name of the package
            version_spec: Optional version specification (e.g., '>=1.0.0')
            
        Returns:
            bool: True if the package is installed with the required version
        """
        if package_name not in self.installed_packages:
            return False
            
        if not version_spec:
            return True
            
        # Parse version spec
        op = version_spec[0] if version_spec[0] in ('=', '>', '<', '!', '~') else '=='
        required_version = version_spec[1:] if op != '=' else version_spec
        
        # Compare versions
        installed_version = self.installed_packages[package_name]
        return self._compare_versions(installed_version, op, required_version)
    
    @staticmethod
    def _get_installed_packages() -> Dict[str, str]:
        """Get a dictionary of installed packages and their versions."""
        try:
            # Use importlib.metadata for Python 3.8+
            return {
                dist.metadata['Name'].lower(): dist.version 
                for dist in importlib.metadata.distributions()
            }
        except (ImportError, AttributeError):
            # Fall back to pkg_resources if importlib.metadata is not available
            import pkg_resources
            return {
                pkg.key.lower(): pkg.version 
                for pkg in pkg_resources.working_set
            }
    
    @staticmethod
    def _install_packages(packages: List[str]) -> bool:
        """Install packages using pip.
        
        Args:
            packages: List of package specifications (e.g., ['package>=1.0.0'])
            
        Returns:
            bool: True if installation was successful, False otherwise
        """
        if not packages:
            return True
            
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *packages])
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install packages: {e}")
            return False
    
    @staticmethod
    def _compare_versions(version1: str, op: str, version2: str) -> bool:
        """Compare two version strings using the specified operator.
        
        Args:
            version1: First version string
            op: Comparison operator ('==', '>=', '<=', '>', '<', '!=')
            version2: Second version string
            
        Returns:
            bool: Result of the comparison
        """
        from packaging import version
        
        v1 = version.parse(version1)
        v2 = version.parse(version2)
        
        if op == '==':
            return v1 == v2
        elif op == '>=':
            return v1 >= v2
        elif op == '<=':
            return v1 <= v2
        elif op == '>':
            return v1 > v2
        elif op == '<':
            return v1 < v2
        elif op == '!=':
            return v1 != v2
        else:
            raise ValueError(f"Unsupported comparison operator: {op}")

def check_and_install_dependencies(install_optional: bool = False) -> bool:
    """Check and optionally install missing dependencies.
    
    Args:
        install_optional: Whether to install optional dependencies
        
    Returns:
        bool: True if all core dependencies are installed, False otherwise
    """
    dep_manager = DependencyManager()
    dep_manager.check_dependencies()
    
    if dep_manager.missing_core or (install_optional and dep_manager.missing_optional):
        print("Some dependencies are missing. Installing...")
        return dep_manager.install_missing_dependencies(install_optional)
    
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Check and install dependencies for auto-screencap")
    parser.add_argument("--install", action="store_true", help="Install missing dependencies")
    parser.add_argument("--optional", action="store_true", help="Include optional dependencies")
    
    args = parser.parse_args()
    
    dep_manager = DependencyManager()
    dep_manager.check_dependencies()
    
    if args.install:
        success = dep_manager.install_missing_dependencies(args.optional)
        if success:
            print("✓ All dependencies installed successfully!")
        else:
            print("Failed to install some dependencies.")
            sys.exit(1)
    else:
        dep_manager.print_status()
