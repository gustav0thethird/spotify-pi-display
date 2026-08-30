# Troubleshooting

## Common Issues and Solutions

### 1. Hotspot Not Starting
**Issue:** The Spotify Display hotspot does not appear when the device is powered on.

**Solution:** Ensure that the device is properly powered and that the setup script (`setup_display.py`) is executed correctly. Check for any error messages in the console output.

### 2. WiFi Connection Failure
**Issue:** The device fails to connect to the home WiFi network.

**Solution:** 
- Verify that the WiFi credentials entered during the setup are correct.
- Ensure that the home WiFi network is operational and within range.
- Restart the device and attempt the connection again.

### 3. Spotify Authorization Issues
**Issue:** The device cannot authorize with Spotify.

**Solution:** 
- Confirm that the `CLIENT_ID` and `CLIENT_SECRET` in the environment variables are set correctly.
- Ensure that the redirect URI (`http://192.168.4.1/callback`) is added to the Spotify app settings on the Spotify Developer Dashboard.
- Check for any network restrictions that might block the authorization process.

### 4. Display Not Updating
**Issue:** The display does not show the currently playing track.

**Solution:** 
- Ensure that the Spotify app is running and that the device is authorized to access the Spotify account.
- Check the network connection to ensure it is stable.
- Restart the display application (`spotify_display.py`) to refresh the connection.

### 5. Font Issues
**Issue:** Fonts are not displaying correctly on the screen.

**Solution:** 
- Verify that the font files specified in the code are present on the device.
- Check the paths in the `setup_display.py` and `spotify_display.py` files to ensure they point to the correct font files.

### 6. Screen Flickering or Artifacts
**Issue:** The display shows flickering or visual artifacts.

**Solution:** 
- Ensure that the framebuffer device (`/dev/fb1`) is correctly configured and accessible.
- Check the power supply to the display; insufficient power can cause display issues.

### 7. Management Portal Access Issues
**Issue:** Unable to access the management portal.

**Solution:** 
- Ensure that you are connected to the Spotify Display hotspot.
- Verify that the correct portal PIN is being used.
- Restart the portal setup script (`setup_portal.py`) if necessary.

### 8. Error Messages in Logs
**Issue:** Error messages are displayed in the console or logs.

**Solution:** 
- Review the error messages for clues on what might be wrong.
- Common issues include missing environment variables, incorrect file paths, or network connectivity problems.
- Consult the relevant sections of the code for additional context on the errors.

### 9. Device Not Responding
**Issue:** The device becomes unresponsive.

**Solution:** 
- Try restarting the device.
- If the issue persists, check for hardware malfunctions or overheating.

### 10. General Debugging Steps
- Ensure all dependencies are installed as specified in the setup instructions.
- Check the device's network configuration and ensure it can reach the internet.
- Review the setup scripts for any configuration errors.

If issues persist after following these troubleshooting steps, consider seeking assistance from the community or checking the GitHub repository for further support.
