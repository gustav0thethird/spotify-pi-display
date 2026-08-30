# Usage

## Management Portal

The management portal for the Spotify Display is accessed via a web interface. To set it up, follow these steps:

1. **Connect to the Hotspot**: Initially, the Raspberry Pi will create a Wi-Fi hotspot named `SpotifyDisplay-hotspot`. Connect your device to this hotspot.

2. **Access the Portal**: Open a web browser and navigate to `http://192.168.4.1`. This will take you to the management portal.

3. **Enter Wi-Fi Credentials**: In the portal, you will be prompted to enter your home Wi-Fi credentials. Fill in the SSID and password.

4. **Connect to Home Wi-Fi**: After entering the credentials, the portal will attempt to connect the Raspberry Pi to your home Wi-Fi. If successful, it will display a QR code for Spotify authorization.

5. **Authorization**: Scan the QR code with your mobile device to authorize the Spotify app. This will redirect you to the Spotify login page where you can log in to your account.

6. **Completion**: Once authorized, the portal will save the token and reboot the Raspberry Pi. You can now access the Spotify Display.

## Interacting with the Spotify Display

Once the setup is complete, the Spotify Display will show the currently playing track from your Spotify account. Here are some key features:

- **Display Information**: The display will show the track title, artist name, and album art.
- **Screensaver Mode**: If the display is idle for a specified duration (default is 5 minutes), it will enter a screensaver mode, blanking the screen.
- **Watchdog Functionality**: The system includes a watchdog that checks the connection to Spotify at regular intervals (default is every 20 seconds).

### Troubleshooting

- If the Raspberry Pi fails to connect to your home Wi-Fi, it will revert to the hotspot mode, allowing you to re-enter the credentials.
- Ensure that the Spotify app credentials (Client ID and Client Secret) are correctly set in the configuration file.

For further assistance, refer to the README.md or the GitHub repository for more detailed documentation.
