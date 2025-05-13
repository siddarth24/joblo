#!/bin/bash

# Check if .env file already exists
if [ -f .env ]; then
  echo "A .env file already exists. Do you want to overwrite it? (y/n)"
  read -r response
  if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "Overwriting .env file..."
  else
    echo "Operation cancelled."
    exit 0
  fi
fi

# Copy the example file
cp .env.example .env

echo "Created .env file from .env.example"
echo "Please edit the .env file and fill in your API keys."

# Open the file in the default editor if on macOS or Linux
if [[ "$OSTYPE" == "darwin"* ]]; then
  open .env
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
  if command -v xdg-open > /dev/null; then
    xdg-open .env
  else
    echo "Please edit the .env file manually."
  fi
else
  echo "Please edit the .env file manually."
fi 