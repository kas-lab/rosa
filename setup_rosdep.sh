#!/bin/bash

# Setup script for ROSA rosdep dependencies on Ubuntu 22.04 (Jammy) with ROS 2 Rolling
# This script adds the custom rosdep.yaml file to the rosdep sources list

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROSDEP_FILE="$SCRIPT_DIR/rosdep.yaml"

echo "Setting up ROSA rosdep dependencies..."

# Check if rosdep.yaml exists
if [ ! -f "$ROSDEP_FILE" ]; then
    echo "Error: rosdep.yaml not found at $ROSDEP_FILE"
    exit 1
fi

# Create rosdep sources directory if it doesn't exist
mkdir -p ~/.ros/rosdep/sources.list.d/

# Add the custom rosdep source
echo "yaml file://$ROSDEP_FILE" > ~/.ros/rosdep/sources.list.d/50-rosa.list

echo "Added ROSA rosdep source to ~/.ros/rosdep/sources.list.d/50-rosa.list"

# Update rosdep database
echo "Updating rosdep database..."
rosdep update

echo "ROSA rosdep setup complete!"
echo ""
echo "You can now run: rosdep install --from-paths src --ignore-src -r -y"