# First-time Setup

## Initial Setup of the Raspberry Pi

1. **Prepare the Raspberry Pi**:
   - Ensure you have a Raspberry Pi with Raspbian installed. You can download the latest version of Raspbian from the official Raspberry Pi website.

2. **Boot the Raspberry Pi**:
   - Insert the microSD card with Raspbian into the Raspberry Pi.
   - Connect the Raspberry Pi to a monitor, keyboard, and power supply.
   - Power on the Raspberry Pi.

3. **Access the Terminal**:
   - Once the Raspberry Pi has booted, open a terminal window.

## Connecting to WiFi

1. **Start the Setup Portal**:
   - Run the setup script by executing the following command in the terminal:
     ```
     python3 files/setup_portal.py
     ```

2. **Connect to the Hotspot**:
   - The Raspberry Pi will create a WiFi hotspot with the IP address `192.168.4.1`.
   - Connect your computer or mobile device to this WiFi network.

3. **Open the Setup Page**:
   - In your web browser, navigate to `http://192.168.4.1`.
   - You will see a setup page where you can enter your home WiFi credentials.

4. **Enter WiFi Credentials**:
   - Fill in the SSID (network name) and password for your home WiFi.
   - Submit the form to initiate the connection process.

5. **Connection Status**:
   - The portal will attempt to connect the Raspberry Pi to your home WiFi.
   - If successful, the portal will display a QR code and the IP address of the Raspberry Pi on your home network.
   - If the connection fails, the hotspot will remain active, allowing you to try again.

6. **Accessing the Display**:
   - Once connected, you can access the Spotify display using the provided IP address or `spotifydisplay.local` in your web browser.

## Final Steps

- After successfully connecting to WiFi, you may need to reboot the Raspberry Pi for all settings to take effect.
- Ensure that you have the necessary Spotify credentials configured in the environment variables as specified in the setup script.
