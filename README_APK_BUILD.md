# Sher Khan World — APK Build

This project includes a GitHub Actions workflow at `.github/workflows/build-apk.yml`.

After uploading this project to a GitHub repository:
1. Open the repository's **Actions** tab.
2. Select **Build Sher Khan World APK**.
3. If needed, select **Run workflow**.
4. Wait for the workflow to finish.
5. Open the completed workflow run and download the **SherKhanWorld-debug-apk** artifact.

This produces a debug APK for phone testing. A Play Store release still requires a properly signed release AAB and the production credentials/integrations described in the project documentation.
