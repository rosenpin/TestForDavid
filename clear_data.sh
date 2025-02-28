#!/bin/bash

# Script to clear photos, metadata, and temp uploads directories
# Usage: ./clear_data.sh

# Set the base data directory
DATA_DIR="data"

# Define directories to clear
PHOTOS_DIR="${DATA_DIR}/photos"
METADATA_DIR="${DATA_DIR}/metadata"
TEMP_UPLOADS_DIR="${DATA_DIR}/temp_uploads"

# Print what we're about to do
echo "This script will clear the following directories:"
echo "- ${PHOTOS_DIR}"
echo "- ${METADATA_DIR}"
echo "- ${TEMP_UPLOADS_DIR}"
echo ""
echo "Press Enter to continue or Ctrl+C to cancel..."
read

# Create directories if they don't exist (to avoid errors)
mkdir -p "${PHOTOS_DIR}"
mkdir -p "${METADATA_DIR}"
mkdir -p "${TEMP_UPLOADS_DIR}"

# Clear the directories
echo "Clearing photos directory..."
rm -rf "${PHOTOS_DIR}"/*
echo "Clearing metadata directory..."
rm -rf "${METADATA_DIR}"/*
echo "Clearing temp uploads directory..."
rm -rf "${TEMP_UPLOADS_DIR}"/*

echo ""
echo "All directories have been cleared successfully!"
echo "You can now start fresh with your photo uploads." 