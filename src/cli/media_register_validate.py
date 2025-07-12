#!/usr/bin/env python3
"""Media Register configuration validation CLI."""

def main():
    """Main entry point for media-register configuration validation."""
    from config_validation.media_register_validate import main as validate_main
    validate_main()


if __name__ == "__main__":
    main()