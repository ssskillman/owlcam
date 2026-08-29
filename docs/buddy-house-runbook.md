# Buddy House Runbook

No Ethernet, monitor, keyboard, or public port forwarding is required.

## Before leaving home

1. Store the home Wi-Fi and phone hotspot profiles on the Pi. Never put either
   password in this repository.
2. Turn on the phone hotspot and verify the Pi can join it.
3. Reconnect the Pi to home Wi-Fi if needed.
4. Verify remote access and camera detection:

   ```bash
   ssh shawn@100.123.8.55
   tailscale status
   nmcli connection show
   rpicam-hello --list-cameras
   ```

To preload the rescue hotspot:

```bash
sudo nmcli dev wifi connect "PHONE_HOTSPOT_SSID" \
  password "PHONE_HOTSPOT_PASSWORD"
```

## At the buddy's house

1. Turn on the known phone hotspot.
2. Power OwlCam and wait 60–120 seconds.
3. Connect over Tailscale:

   ```bash
   ssh shawn@100.123.8.55
   ```

4. Scan and join the buddy's Wi-Fi:

   ```bash
   nmcli dev wifi rescan
   nmcli dev wifi list
   sudo nmcli dev wifi connect "BUDDYS_WIFI_SSID" \
     password "BUDDYS_WIFI_PASSWORD"
   ```

   The SSH session may drop while Wi-Fi switches.

5. Wait 10–30 seconds, reconnect, and verify:

   ```bash
   ssh shawn@100.123.8.55
   hostname
   hostname -I
   tailscale ip -4
   tailscale status
   nmcli connection show --active
   rpicam-hello --list-cameras
   ```

6. Start the Phase 0 manual stream if service automation has not yet been
   deployed. Follow the exact commands in the repository README.
7. From an authorized Tailscale device, open:
   `http://100.123.8.55:8888/owl`.

## Viewer access

Share only the `owlcam` Tailscale machine with the buddy's own Tailscale
account. Do not share the `shawn` Linux account or the entire personal tailnet
for viewing. SSH access is administrative and should not be granted solely to
watch the stream.
