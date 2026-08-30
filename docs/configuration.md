# Configuration

This document outlines the configuration details for the `spotify-pi-display` project, including environment variables and inventory setup.

## Environment Variables

The following environment variables must be set in the `group_vars/all.yml` file:

- `boot_config`: Specifies the boot configuration path. Use `/boot/firmware/config.txt` on Bookworm and `/boot/config.txt` on Bullseye.
  
  ```yaml
  boot_config: /boot/firmware/config.txt
  ```

- `app_dir`: Defines the application directory where the Spotify display will be installed. Replace `YOUR_USERNAME` with the actual username.

  ```yaml
  app_dir: /home/YOUR_USERNAME/spotify-display
  ```

- `spotify_client_id`: Your Spotify application client ID. This is obtained by creating an app at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard). Ensure to add `http://192.168.4.1/callback` as a Redirect URI for the app.

  ```yaml
  spotify_client_id: "YOUR_SPOTIFY_CLIENT_ID"
  ```

- `spotify_client_secret`: Your Spotify application client secret. This is also obtained from the Spotify Developer Dashboard.

  ```yaml
  spotify_client_secret: "YOUR_SPOTIFY_CLIENT_SECRET"
  ```

- `portal_pin`: A PIN required to access the management portal. It is recommended to change this value before deploying the application.

  ```yaml
  portal_pin: "YOUR_PORTAL_PIN"
  ```

## Inventory Setup

The inventory for the project is defined in the `inventory.ini` file. Ensure that the necessary hosts and groups are specified according to your deployment environment. The structure typically includes the following:

```ini
[all]
your_host_name ansible_host=your_host_ip

[webservers]
your_web_server ansible_host=your_web_server_ip
```

Make sure to replace `your_host_name`, `your_host_ip`, `your_web_server`, and `your_web_server_ip` with the actual values relevant to your setup.

This configuration is essential for the proper functioning of the `spotify-pi-display` application. Ensure all values are correctly set before proceeding with deployment.
