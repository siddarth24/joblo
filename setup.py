#!/usr/bin/env python3
"""
Setup script to initialize the required directories and environment for Joblo.
"""

import os
import sys
from dotenv import load_dotenv

# Define required directories
REQUIRED_DIRS = ["uploads", "linkedin_states", "logs"]


def main():
    """Create required directories and check for necessary environment variables."""
    load_dotenv()
    print("Setting up Joblo environment...")

    # Create required directories
    for directory in REQUIRED_DIRS:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")
        else:
            print(f"Directory already exists: {directory}")

    # Check for required environment variables
    required_env_vars = ["OPENAI_API_KEY", "GROQ_API_KEY", "CLOUDCONVERT_API_KEY"]
    missing_vars = []

    for var in required_env_vars:
        if not os.environ.get(var):
            missing_vars.append(var)

    if missing_vars:
        print("\nWARNING: The following required environment variables are not set:")
        for var in missing_vars:
            print(f"  - {var}")
        print(
            "\nPlease set these variables in your environment or .env file for the setup script to verify."
        )
        print(
            "Note: Your main application might still load them correctly if it uses dotenv."
        )
    else:
        print(
            "\nAll required environment variables appear to be set according to the .env file."
        )

    print("\nSetup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
