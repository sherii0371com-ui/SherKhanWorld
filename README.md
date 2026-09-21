name: Build Sher Khan World APK

on:
  workflow_dispatch:
  push:
    branches:
      - main

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '17'

      - name: Find and extract project ZIP
        run: |
          ZIP_FILE=$(find . -maxdepth 2 -type f -name "*.zip" | head -n 1)
          if [ -z "$ZIP_FILE" ]; then
            echo "No ZIP file found."
            exit 1
          fi
          mkdir -p android-project
          unzip -q "$ZIP_FILE" -d android-project
          echo "Project extracted."

      - name: Find Gradle project
        run: |
          GRADLEW=$(find android-project -type f -name "gradlew" | head -n 1)
          if [ -z "$GRADLEW" ]; then
            echo "gradlew not found."
            exit 1
          fi
          PROJECT_DIR=$(dirname "$GRADLEW")
          echo "PROJECT_DIR=$PROJECT_DIR" >> $GITHUB_ENV

      - name: Make Gradle executable
        run: chmod +x "$PROJECT_DIR/gradlew"

      - name: Build APK
        run: |
          cd "$PROJECT_DIR"
          ./gradlew assembleDebug --no-daemon

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: Sher-Khan-World-APK
          path: "**/build/outputs/apk/**/*.apk"
