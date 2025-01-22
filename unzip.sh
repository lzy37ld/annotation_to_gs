#!/bin/bash

# Check if a zip file is provided as an argument
if [ -z "$1" ]; then
    echo "Please provide a zip file path as an argument."
    exit 1
fi

ZIP_FILE="$1"
PARENT_DIR="$(dirname "$ZIP_FILE")"
FOLDER_NAME="${ZIP_FILE%.zip}"

# Unzip the main zip file to its parent directory
unzip "$ZIP_FILE" -d "$PARENT_DIR"
if [ $? -ne 0 ]; then
    echo "Failed to unzip the main zip file. Please check the file."
    exit 1
fi

# Remove the main zip file after extraction
rm -f "$ZIP_FILE"

# Navigate to the extracted folder
cd "$FOLDER_NAME" || { echo "Unable to enter the folder $FOLDER_NAME."; exit 1; }

# Process each zip file in the folder
for file in *.zip; do
    if [ -f "$file" ]; then
        TARGET_FOLDER="${file%.zip}"
        mkdir -p "$TARGET_FOLDER"
        unzip "$file" -d "$TARGET_FOLDER"
        if [ $? -eq 0 ]; then
            echo "\"$file\" extracted to \"$TARGET_FOLDER\" successfully"
        else
            echo "\"$file\" extraction failed"
        fi
        # Remove the zip file after extraction
        rm -f "$file"
    fi
done

# Return to the original directory
cd - > /dev/null

echo "All operations are complete."
