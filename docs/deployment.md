# Deployment

This document provides instructions for deploying the Spotify Display using Ansible.

## Prerequisites

Ensure you have the following before proceeding with the deployment:

- Ansible installed on your control machine.
- Access to a Raspberry Pi configured for deployment.

## Inventory Configuration

1. Edit the `inventory.ini` file to specify the target Raspberry Pi. Ensure it includes the correct IP address or hostname.

## Ansible Playbook

The deployment is managed through the `playbook.yml` file. This playbook includes tasks to set up the Spotify Display on the Raspberry Pi.

### Running the Playbook

To execute the playbook, run the following command from your terminal:

```bash
ansible-playbook -i inventory.ini playbook.yml
```

### Playbook Breakdown

The playbook consists of several tasks organized into phases:

#### Phase 1: System Packages

- **Set Hostname**: The hostname is set to `spotifydisplay`.
- **Update /etc/hosts**: The `/etc/hosts` file is updated with the new hostname.
- **Create App Directory**: An application directory is created with the appropriate permissions.
- **Update APT Cache**: The APT cache is updated to ensure the latest package information is available.
- **Install System Packages**: Required system packages are installed, including Python and other dependencies.
- **Disable System dnsmasq**: The system dnsmasq service is disabled to prevent conflicts with Network Manager.
- **Install Python Packages**: Necessary Python packages are installed using pip.

#### Phase 1.5: Disable First-Boot Wizard

- **Mark System as Configured**: A file is created to suppress the Raspberry Pi welcome wizard.
- **Remove Autostart Entries**: Autostart entries for the Pi wizard are removed.
- **Disable Firstboot Services**: Services related to the first boot are disabled.
- **Mask Firstboot Services**: Certain services are masked to prevent them from starting.
- **Clear MOTD and Login Banner**: The message of the day and login banner are cleared.

## Additional Configuration

If further customization is needed, you can modify the `group_vars/all.yml` file to adjust variables used in the playbook.

## Conclusion

After running the playbook, the Spotify Display should be set up and ready for use on your Raspberry Pi. Ensure to verify the installation and functionality as needed.
