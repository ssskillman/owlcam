# Buddy House Runbook

No Ethernet, monitor, keyboard, or public port forwarding is required.
The camera needs *some* internet (buddy Wi-Fi or your phone hotspot) so
Tailscale, Funnel, and the live page can answer.

Watch URL: <https://owlcam.tail31318f.ts.net/>

That is the same public page you use at home. HLS never binds to the LAN, so
do **not** open `http://100.123.8.55:8888/owl` — that port is loopback-only.

## Before leaving home

1. Store the home Wi-Fi and phone hotspot profiles on the Pi. Never put either
   password in this repository.
2. Turn on the phone hotspot and verify the Pi can join it.
3. Reconnect the Pi to home Wi-Fi if needed.
4. Confirm the units are installed and Funnel is the mode you want:

   ```bash
   ssh shawn@100.123.8.55
   tailscale status
   nmcli connection show
   rpicam-hello --list-cameras
   systemctl --user is-active \
     owlcam-mediamtx owlcam-stream owlcam-site owlcam-diagnostics
   /home/shawn/owlcam/deploy/pi/scripts/publish-feed.sh --status
   ```

   `--public` means anyone with the URL can watch, including phones with no
   Tailscale. `--private` means only devices signed into the tailnet.

To preload the rescue hotspot:

```bash
sudo nmcli dev wifi connect "PHONE_HOTSPOT_SSID" \
  password "PHONE_HOTSPOT_PASSWORD"
```

## At the buddy's house

1. Turn on the known phone hotspot.
2. Power OwlCam and wait 60–120 seconds for Tailscale to come up.
3. Connect over Tailscale (this still works while the Pi is on the hotspot):

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
   systemctl --user is-active \
     owlcam-mediamtx owlcam-stream owlcam-site owlcam-diagnostics
   curl -sSL -o /dev/null -w '%{http_code}\n' \
     http://127.0.0.1:8080/
   curl -sSL -o /dev/null -w '%{http_code}\n' \
     http://127.0.0.1:8888/owl/index.m3u8
   ```

   Local `200`s mean the camera and page are serving. The public URL depends on
   Funnel plus the house upload, so check that next from a phone that is *not*
   on Tailscale:

   ```text
   https://owlcam.tail31318f.ts.net/
   ```

6. If the units are not installed, install them once rather than running the
   old one-shot capture:

   ```bash
   cd /home/shawn/owlcam/deploy
   ./pi/scripts/install-services.sh
   ```

   Do not also run `serve-stream.sh` or the UDP publisher. They fight the unit
   for the sensor.

## Viewer access

**Funnel on (`publish-feed.sh --public`):** send the buddy
<https://owlcam.tail31318f.ts.net/>. No Tailscale account, no IP sharing.
That is the intended path for a nature cam.

**Funnel off (`publish-feed.sh --private`):** share only the `owlcam`
Tailscale *machine* with the buddy's own Tailscale account. Do not share the
`shawn` Linux account or the entire personal tailnet just to watch. SSH is
administrative and should not be granted solely to watch the stream.

If the buddy Wi-Fi has no outbound path that Funnel can use, fall back to the
phone hotspot and keep Funnel on, or switch to `--private` and have the buddy
join Tailscale.
