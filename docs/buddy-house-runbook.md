# Buddy House Runbook

No Ethernet, monitor, keyboard, or public port forwarding is required.
The camera needs *some* internet (buddy Wi-Fi or your phone hotspot) so
Tailscale, Funnel, and the live page can answer.

Watch URL: <https://carver-owlcam-72343.web.app> (redirects to the Pi at
<https://owlcam.tail31318f.ts.net/>; either address works)

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
     owlcam-mediamtx owlcam-stream owlcam-site owlcam-diagnostics owlcam-admin
   /home/shawn/owlcam/deploy/pi/scripts/publish-feed.sh --status
   ```

   `--public` means anyone with the URL can watch, including phones with no
   Tailscale. `--private` means only devices signed into the tailnet.

To preload the rescue hotspot. `--ask` prompts for the password instead of
leaving it in shell history:

```bash
sudo nmcli --ask device wifi connect "PHONE_HOTSPOT_SSID" ifname wlan0
sudo nmcli connection modify "PHONE_HOTSPOT_SSID" \
  connection.autoconnect yes connection.autoconnect-priority 10
sudo nmcli connection modify "HOME_WIFI_SSID" \
  connection.autoconnect yes connection.autoconnect-priority 50
```

Priority picks the winner when both are in range, so home Wi-Fi stays preferred
and the hotspot is the fallback.

**Step 1 is not optional.** NetworkManager never joins an SSID it has no saved
profile for, so a hotspot that was never preloaded is indistinguishable from a
dead Pi: Tailscale offline, no SSH, no `.local`. Preloading is the whole reason
the trip works.

**Do not run `nmcli device wifi connect` over SSH on a Wi-Fi-only Pi.** It drops
the connection carrying your session before it knows the new network works, and
a failed join leaves the Pi stranded with no network and no way back in. Plug in
Ethernet first as a lifeline, or create the profile without activating it:

```bash
read -rsp 'Hotspot password: ' PSK; echo
sudo nmcli connection add type wifi con-name rescue-hotspot ifname wlan0 \
  ssid "PHONE_HOTSPOT_SSID" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK" \
  connection.autoconnect yes connection.autoconnect-priority 10
unset PSK
```

iOS specifics worth knowing: turn on **Maximize Compatibility** so the hotspot
broadcasts 2.4 GHz, which reaches further than 5 GHz, and keep the Personal
Hotspot screen open while the Pi boots, because iOS powers the radio down when
no client is connected. That screen's device count is the fastest way to tell
whether the Pi joined.

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
     owlcam-mediamtx owlcam-stream owlcam-site owlcam-diagnostics owlcam-admin
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

## If the Pi has no network

Tailscale reporting `offline` together with `ssh: owlcam.local: Unknown host`
means the Pi has no network at all, not that a service crashed. There is no
remote path in, because SSH, Tailscale, and mDNS all depend on the thing that is
missing. `owlcam.local` also only resolves on the same LAN, so it can never
reach a Pi on a hotspot from a laptop on house Wi-Fi — use the Tailscale
address, which works across networks.

Recover with physical access, cheapest first:

1. **Ethernet.** Plug the Pi into any router with a free port. DHCP and
   Tailscale come up within a minute or two, then `ssh shawn@100.123.8.55`.
   Leave the cable in while fixing Wi-Fi so a failed join cannot strand it
   again.
2. **Hotspot, but only if a profile already exists.** Maximize Compatibility on,
   Personal Hotspot screen open, then power cycle the Pi and wait two minutes.
3. **Local console.** micro-HDMI, a monitor, and a USB keyboard.

Editing the SD card on a Mac is not a shortcut. This Pi runs Debian 13 with
NetworkManager, so a `wpa_supplicant.conf` dropped in the boot partition is
ignored, and the profiles live on an ext4 root filesystem that macOS cannot
mount without extra software.

## Viewer access

**Funnel on (`publish-feed.sh --public`):** send the buddy
<https://carver-owlcam-72343.web.app>. No Tailscale account, no IP sharing.
That is the intended path for a nature cam. The redirect is the better link to
text someone, since it survives a hostname change on the Pi.

**Funnel off (`publish-feed.sh --private`):** share only the `owlcam`
Tailscale *machine* with the buddy's own Tailscale account. Do not share the
`shawn` Linux account or the entire personal tailnet just to watch. SSH is
administrative and should not be granted solely to watch the stream.

If the buddy Wi-Fi has no outbound path that Funnel can use, fall back to the
phone hotspot and keep Funnel on, or switch to `--private` and have the buddy
join Tailscale.
