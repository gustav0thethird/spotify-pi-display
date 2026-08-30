# Display States

This document provides an overview of the different display states used in the Spotify Pi Display application, detailing their meanings and functions.

## Overview of Display States

The application utilizes a state machine to manage various display states during the setup and operation of the Spotify display. Below are the defined states:

### SPINNING
- **Description**: This state indicates that the system is waiting for the hotspot to become active. It typically features an animated spinner to inform the user that the system is in the process of establishing a connection.

### PROGRESS
- **Description**: In this state, the hotspot has been confirmed, and a progress bar is animated to indicate that the system is connecting to the home WiFi. This state provides visual feedback to the user that the connection process is underway.

### QR1
- **Description**: This is the first phase of the QR code display. The user is prompted to scan a QR code to join the SpotifyDisplay hotspot. This state is crucial for initiating the connection process to the Spotify service.

### WIFI_CONNECTING
- **Description**: This state occurs when the hotspot connection has been dropped, and the system is attempting to connect to the home WiFi. It indicates that the system is actively trying to establish a stable internet connection.

### QR2
- **Description**: This is the second phase of the QR code display. The user is prompted to scan a second QR code to authorize the Spotify application. This step is necessary for granting the application access to the user's Spotify account.

## State Transitions
The application transitions between these states based on user actions and system events, such as successful connections or errors encountered during the setup process. The transitions are designed to guide the user through the setup and ensure a smooth experience. 

## Conclusion
Understanding these display states is essential for troubleshooting and effectively using the Spotify Pi Display application. Each state serves a specific purpose in the setup and operation of the device, providing necessary feedback to the user throughout the process.
