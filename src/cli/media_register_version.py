#!/usr/bin/env python3
"""
Version management for Media Register infrastructure patterns.

This module provides utilities for semantic versioning and compatibility checking.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class VersionType(Enum):
    """Version change types following semantic versioning."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


@dataclass(frozen=True)
class Version:
    """Represents a semantic version."""
    major: int
    minor: int
    patch: int
    pre_release: Optional[str] = None
    build_metadata: Optional[str] = None
    
    def __str__(self) -> str:
        """String representation of the version."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release:
            version += f"-{self.pre_release}"
        if self.build_metadata:
            version += f"+{self.build_metadata}"
        return version
    
    def __eq__(self, other: 'Version') -> bool:
        """Check if versions are equal."""
        return (
            self.major == other.major and
            self.minor == other.minor and
            self.patch == other.patch and
            self.pre_release == other.pre_release
        )
    
    def __lt__(self, other: 'Version') -> bool:
        """Check if this version is less than another."""
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch
        
        # Handle pre-release versions
        if self.pre_release is None and other.pre_release is not None:
            return False
        if self.pre_release is not None and other.pre_release is None:
            return True
        if self.pre_release is not None and other.pre_release is not None:
            return self.pre_release < other.pre_release
        
        return False
    
    def __le__(self, other: 'Version') -> bool:
        """Check if this version is less than or equal to another."""
        return self == other or self < other
    
    def __gt__(self, other: 'Version') -> bool:
        """Check if this version is greater than another."""
        return not self <= other
    
    def __ge__(self, other: 'Version') -> bool:
        """Check if this version is greater than or equal to another."""
        return not self < other
    
    def bump(self, version_type: VersionType) -> 'Version':
        """Create a new version with the specified bump."""
        if version_type == VersionType.MAJOR:
            return Version(self.major + 1, 0, 0)
        elif version_type == VersionType.MINOR:
            return Version(self.major, self.minor + 1, 0)
        elif version_type == VersionType.PATCH:
            return Version(self.major, self.minor, self.patch + 1)
        else:
            raise ValueError(f"Invalid version type: {version_type}")
    
    def is_compatible_with(self, other: 'Version') -> bool:
        """
        Check if this version is compatible with another using semantic versioning rules.
        
        Compatible means:
        - Same major version
        - This version is >= other version
        """
        return self.major == other.major and self >= other


class VersionManager:
    """Manages versioning for infrastructure patterns."""
    
    # Current version of the patterns
    CURRENT_VERSION = Version(1, 0, 0)
    
    # Minimum required dependency versions
    MIN_CDK_VERSION = Version(2, 120, 0)
    MIN_PYTHON_VERSION = Version(3, 9, 0)
    
    # Version compatibility matrix
    COMPATIBILITY_MATRIX = {
        Version(1, 0, 0): {
            "cdk": Version(2, 120, 0),
            "python": Version(3, 9, 0),
            "aws_cli": Version(2, 0, 0),
        }
    }
    
    @classmethod
    def parse_version(cls, version_string: str) -> Version:
        """Parse a version string into a Version object."""
        # Semantic version regex
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$'
        match = re.match(pattern, version_string)
        
        if not match:
            raise ValueError(f"Invalid version string: {version_string}")
        
        major, minor, patch, pre_release, build_metadata = match.groups()
        
        return Version(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            pre_release=pre_release,
            build_metadata=build_metadata,
        )
    
    @classmethod
    def get_current_version(cls) -> Version:
        """Get the current version of the patterns."""
        return cls.CURRENT_VERSION
    
    @classmethod
    def check_cdk_compatibility(cls, cdk_version: str) -> bool:
        """Check if the given CDK version is compatible."""
        try:
            version = cls.parse_version(cdk_version)
            return version >= cls.MIN_CDK_VERSION
        except ValueError:
            return False
    
    @classmethod
    def check_python_compatibility(cls, python_version: str) -> bool:
        """Check if the given Python version is compatible."""
        try:
            # Handle Python version format (e.g., "3.9.7" -> "3.9.7")
            version = cls.parse_version(python_version)
            return version >= cls.MIN_PYTHON_VERSION
        except ValueError:
            return False
    
    @classmethod
    def get_compatibility_info(cls, pattern_version: Optional[Version] = None) -> Dict[str, Version]:
        """Get compatibility information for a specific pattern version."""
        version = pattern_version or cls.CURRENT_VERSION
        return cls.COMPATIBILITY_MATRIX.get(version, {})
    
    @classmethod
    def validate_environment(cls) -> List[str]:
        """
        Validate the current environment for compatibility.
        
        Returns:
            List of compatibility issues (empty if all good)
        """
        issues = []
        
        try:
            import sys
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            if not cls.check_python_compatibility(python_version):
                issues.append(f"Python {python_version} is not compatible. Minimum required: {cls.MIN_PYTHON_VERSION}")
        except Exception as e:
            issues.append(f"Could not determine Python version: {e}")
        
        # Check CDK version if available
        try:
            import subprocess
            result = subprocess.run(["cdk", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                # Extract version from output like "2.120.0 (build 4f06d2c)"
                cdk_output = result.stdout.strip()
                version_match = re.search(r'(\d+\.\d+\.\d+)', cdk_output)
                if version_match:
                    cdk_version = version_match.group(1)
                    if not cls.check_cdk_compatibility(cdk_version):
                        issues.append(f"CDK {cdk_version} is not compatible. Minimum required: {cls.MIN_CDK_VERSION}")
                else:
                    issues.append("Could not parse CDK version from output")
            else:
                issues.append("CDK CLI not found or not working")
        except FileNotFoundError:
            issues.append("CDK CLI not found in PATH")
        except Exception as e:
            issues.append(f"Could not check CDK version: {e}")
        
        return issues
    
    @classmethod
    def get_upgrade_path(cls, from_version: Version, to_version: Version) -> List[str]:
        """
        Get the upgrade path between two versions.
        
        Returns:
            List of upgrade steps and warnings
        """
        upgrade_steps = []
        
        if from_version > to_version:
            return ["Cannot downgrade. Use a fresh deployment."]
        
        if from_version == to_version:
            return ["Already at target version."]
        
        # Check for breaking changes
        if from_version.major < to_version.major:
            upgrade_steps.append("⚠️  BREAKING CHANGES: Major version upgrade detected")
            upgrade_steps.append("📖 Review CHANGELOG.md for breaking changes")
            upgrade_steps.append("🧪 Test in non-production environment first")
        
        # Version-specific upgrade steps
        if from_version < Version(1, 0, 0) and to_version >= Version(1, 0, 0):
            upgrade_steps.extend([
                "1. Update configuration files to new YAML format",
                "2. Replace L2 constructs with L3 patterns",
                "3. Update import statements",
                "4. Run configuration validation",
                "5. Deploy to development environment first",
            ])
        
        return upgrade_steps
    
    @classmethod
    def generate_release_notes(cls, version: Version, changes: Dict[str, List[str]]) -> str:
        """Generate release notes for a version."""
        release_notes = []
        release_notes.append(f"# Release {version}")
        release_notes.append("")
        
        # Add sections in order
        sections = [
            ("Added", "### ✨ Added"),
            ("Changed", "### 🔄 Changed"), 
            ("Deprecated", "### ⚠️ Deprecated"),
            ("Removed", "### 🗑️ Removed"),
            ("Fixed", "### 🐛 Fixed"),
            ("Security", "### 🔒 Security"),
        ]
        
        for section_key, section_title in sections:
            if section_key in changes and changes[section_key]:
                release_notes.append(section_title)
                release_notes.append("")
                for change in changes[section_key]:
                    release_notes.append(f"- {change}")
                release_notes.append("")
        
        # Add compatibility information
        compat_info = cls.get_compatibility_info(version)
        if compat_info:
            release_notes.append("### 📋 Compatibility")
            release_notes.append("")
            for dep, min_version in compat_info.items():
                release_notes.append(f"- {dep.upper()}: {min_version}+")
            release_notes.append("")
        
        return "\n".join(release_notes)


def main():
    """CLI for version management."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Media Register Version Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Current version command
    current_parser = subparsers.add_parser("current", help="Show current version")
    
    # Validate environment command
    validate_parser = subparsers.add_parser("validate", help="Validate environment compatibility")
    
    # Check compatibility command
    compat_parser = subparsers.add_parser("check", help="Check version compatibility")
    compat_parser.add_argument("--cdk", help="CDK version to check")
    compat_parser.add_argument("--python", help="Python version to check")
    
    # Upgrade path command
    upgrade_parser = subparsers.add_parser("upgrade", help="Show upgrade path")
    upgrade_parser.add_argument("from_version", help="Current version")
    upgrade_parser.add_argument("to_version", help="Target version")
    
    args = parser.parse_args()
    
    if args.command == "current":
        print(f"Current version: {VersionManager.get_current_version()}")
    
    elif args.command == "validate":
        issues = VersionManager.validate_environment()
        if issues:
            print("❌ Environment compatibility issues:")
            for issue in issues:
                print(f"  • {issue}")
            exit(1)
        else:
            print("✅ Environment is compatible")
    
    elif args.command == "check":
        if args.cdk:
            if VersionManager.check_cdk_compatibility(args.cdk):
                print(f"✅ CDK {args.cdk} is compatible")
            else:
                print(f"❌ CDK {args.cdk} is not compatible (minimum: {VersionManager.MIN_CDK_VERSION})")
        
        if args.python:
            if VersionManager.check_python_compatibility(args.python):
                print(f"✅ Python {args.python} is compatible")
            else:
                print(f"❌ Python {args.python} is not compatible (minimum: {VersionManager.MIN_PYTHON_VERSION})")
    
    elif args.command == "upgrade":
        try:
            from_ver = VersionManager.parse_version(args.from_version)
            to_ver = VersionManager.parse_version(args.to_version)
            
            steps = VersionManager.get_upgrade_path(from_ver, to_ver)
            print(f"Upgrade path from {from_ver} to {to_ver}:")
            for step in steps:
                print(f"  {step}")
        except ValueError as e:
            print(f"❌ Invalid version: {e}")
            exit(1)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()