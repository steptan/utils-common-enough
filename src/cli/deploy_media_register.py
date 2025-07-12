#!/usr/bin/env python3
"""Media Register deployment CLI module."""

import os
import sys


def main():
    """Main entry point for media-register deployment."""
    # Set project-specific defaults
    os.environ.setdefault("PROJECT_NAME", "media-register")
    
    # Import and call the main deploy function
    from cli.deploy import main as deploy_main
    
    # Call the deploy main function
    deploy_main()


if __name__ == "__main__":
    main()