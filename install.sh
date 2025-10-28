#!/bin/bash

# Panasonic Aquarea Home Assistant Integration Installer
# This script installs the custom integration to your Home Assistant instance

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🏠 Panasonic Aquarea Home Assistant Integration Installer${NC}"
echo "=================================================="

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Home Assistant config directory exists
if [ -z "$1" ]; then
    print_info "Please provide the path to your Home Assistant config directory"
    print_info "Usage: ./install.sh /path/to/homeassistant/config"
    print_info "Example: ./install.sh ~/.homeassistant"
    print_info "         ./install.sh /usr/share/hassio/homeassistant"
    exit 1
fi

CONFIG_DIR="$1"

if [ ! -d "$CONFIG_DIR" ]; then
    print_error "Home Assistant config directory not found: $CONFIG_DIR"
    exit 1
fi

print_success "Found Home Assistant config directory: $CONFIG_DIR"

# Create custom_components directory if it doesn't exist
CUSTOM_COMPONENTS_DIR="$CONFIG_DIR/custom_components"
if [ ! -d "$CUSTOM_COMPONENTS_DIR" ]; then
    print_info "Creating custom_components directory..."
    mkdir -p "$CUSTOM_COMPONENTS_DIR"
fi

# Create the integration directory
INTEGRATION_DIR="$CUSTOM_COMPONENTS_DIR/panasonic_aquarea"
print_info "Installing integration to: $INTEGRATION_DIR"

# Remove existing installation if present
if [ -d "$INTEGRATION_DIR" ]; then
    print_warning "Existing installation found. Removing..."
    rm -rf "$INTEGRATION_DIR"
fi

# Copy integration files
print_info "Copying integration files..."
cp -r "custom_components/panasonic_aquarea" "$CUSTOM_COMPONENTS_DIR/"

print_success "Integration files copied successfully!"

# Check if aioaquarea is available in the environment
print_info "Checking for aioaquarea library..."
python3 -c "import aioaquarea; print('aioaquarea version available')" 2>/dev/null || {
    print_warning "aioaquarea library not found in system Python"
    print_info "Home Assistant will install it automatically when the integration loads"
}

# Set proper permissions
print_info "Setting proper permissions..."
chmod -R 644 "$INTEGRATION_DIR"
find "$INTEGRATION_DIR" -type d -exec chmod 755 {} \;

print_success "Installation completed successfully!"
echo ""
print_info "Next steps:"
echo "1. Restart Home Assistant"
echo "2. Go to Settings → Devices & Services"
echo "3. Click 'Add Integration' and search for 'Panasonic Aquarea'"
echo "4. Enter your Panasonic Smart Cloud credentials"
echo ""
print_info "Your device 'Langagervej' should be discovered automatically!"
echo ""
print_warning "Note: Make sure to restart Home Assistant before configuring the integration."