#!/bin/bash

# Validation script to check if ROSA rosdep dependencies are properly configured
# This helps users verify that the rosdep setup worked correctly

echo "Validating ROSA rosdep configuration..."

# Check if rosdep sources file exists
ROSDEP_SOURCE_FILE="$HOME/.ros/rosdep/sources.list.d/50-rosa.list"
if [ ! -f "$ROSDEP_SOURCE_FILE" ]; then
    echo "✗ ROSA rosdep source file not found at $ROSDEP_SOURCE_FILE"
    echo "  Please run ./setup_rosdep.sh first"
    exit 1
fi

echo "✓ ROSA rosdep source file found"

# Test key dependencies to see if rosdep can resolve them
TEST_DEPS=("behaviortree_cpp" "popf" "launch_pytest" "rclcpp_cascade_lifecycle" "tf_transformations")
FAILED_DEPS=()

echo "Testing dependency resolution..."

for dep in "${TEST_DEPS[@]}"; do
    if rosdep resolve "$dep" >/dev/null 2>&1; then
        echo "  ✓ $dep - resolved"
    else
        echo "  ✗ $dep - failed to resolve"
        FAILED_DEPS+=("$dep")
    fi
done

if [ ${#FAILED_DEPS[@]} -eq 0 ]; then
    echo ""
    echo "🎉 All ROSA dependencies are properly configured!"
    echo "You can now run: rosdep install --from-paths src --ignore-src -r -y"
else
    echo ""
    echo "⚠ Some dependencies failed to resolve: ${FAILED_DEPS[*]}"
    echo "This might be normal if you're not on Ubuntu 22.04 (Jammy) with ROS 2 Rolling"
    echo "Try running: rosdep update"
fi