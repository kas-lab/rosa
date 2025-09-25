#!/bin/bash

# Setup script for ROSA rosdep dependencies on Ubuntu 22.04 (Jammy) with ROS 2 Rolling
# This script adds the custom rosdep.yaml file to the rosdep sources list

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROSDEP_FILE="$SCRIPT_DIR/rosdep.yaml"
ROSDEP_SOURCE_FILE="$HOME/.ros/rosdep/sources.list.d/50-rosa.list"

echo "Setting up ROSA rosdep dependencies for Ubuntu 22.04 (Jammy)..."

# Check if rosdep.yaml exists
if [ ! -f "$ROSDEP_FILE" ]; then
    echo "Error: rosdep.yaml not found at $ROSDEP_FILE"
    exit 1
fi

# Check if rosdep is installed
if ! command -v rosdep &> /dev/null; then
    echo "Error: rosdep is not installed. Please install it with:"
    echo "  sudo apt update && sudo apt install python3-rosdep"
    exit 1
fi

# Create rosdep sources directory if it doesn't exist
mkdir -p ~/.ros/rosdep/sources.list.d/

# Add the custom rosdep source
echo "yaml file://$ROSDEP_FILE" > "$ROSDEP_SOURCE_FILE"

echo "✓ Added ROSA rosdep source to $ROSDEP_SOURCE_FILE"

# Initialize rosdep if not already done (ignore errors if already initialized)
echo "Initializing rosdep (if needed)..."
rosdep init 2>/dev/null || echo "rosdep already initialized"

# Update rosdep database
echo "Updating rosdep database..."
if rosdep update; then
    echo "✓ rosdep database updated successfully"
else
    echo "⚠ Warning: rosdep update encountered issues, but continuing..."
fi

echo ""
echo "🎉 ROSA rosdep setup complete!"
echo ""
echo "You can now run:"
echo "  rosdep install --from-paths src --ignore-src -r -y"
echo ""
echo "If you encounter any issues, check the troubleshooting section in README.md"