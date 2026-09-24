# INMP441 I²S microphone

Standalone capture for the nest-box INMP441 on the Raspberry Pi 4. Video/audio
mux, live HLS audio, and the web UI are **not** part of this slice.

## Wiring

3.3 V only. Do not use 5 V.

| INMP441 | Pi signal | BCM GPIO | Physical pin |
|---|---|---:|---:|
| VDD | 3.3V | — | 1 |
| GND | GND | — | 6 |
| SCK | PCM_CLK / I²S BCLK | GPIO18 | 12 |
| WS | PCM_FS / I²S LRCLK | GPIO19 | 35 |
| SD | PCM_DIN | GPIO20 | 38 |
| L/R | GND | — | shared GND |

L/R tied to GND is left-channel / single-mic. Do not flip it to 3.3 V unless a
proven format still records silence. I²C for the BME280 stays on GPIO2/3.

## Boot configuration

Inspect `/boot/firmware/config.txt` (this Pi) before editing. Overlay names
come from `/boot/firmware/overlays/README` on the device, not from memory.

Working configuration on `owlcam` (Debian 13 / kernel 6.18, 2026-09-23):

```ini
dtparam=i2s=on
dtoverlay=googlevoicehat-soundcard
```

`dtparam=audio=on` (headphone PWM) was left enabled. Disable it only if the
I²S card fails to bind after reboot.

Backup and apply on the Pi:

```bash
sudo /home/shawn/owlcam/deploy/pi/scripts/configure-i2s-mic.sh
# review the printed diff, then
sudo /home/shawn/owlcam/deploy/pi/scripts/configure-i2s-mic.sh --reboot
```

The script writes a timestamped `config.txt.backup.*` beside the live file and
does not strip camera or I²C lines.

## ALSA

After reboot, `arecord -l` lists:

```text
card 1: sndrpigooglevoi [snd_rpi_googlevoicehat_soundcar], device 0: Google voiceHAT SoundCard HiFi voicehat-hifi-0
```

Card **numbers** move when the USB camera enumerates; use the short name
`sndrpigooglevoi`. The hardware PCM is **stereo S32_LE at 48 kHz only**
(`FRAME_BITS: 64`). Direct `arecord -c 1 -D hw:...` fails. `owlmic` is a plug
that takes the left channel (L/R strapped to GND).

```bash
./pi/scripts/configure-owlmic.sh
arecord -D owlmic -c 1 -r 48000 -f S32_LE -d 10 ~/owlcam/audio_tests/check.wav
```

That writes `~/.asoundrc` with `pcm.owlmic` → `dsnoop` → `hw:sndrpigooglevoi,0`.
An ALSA capture device only admits one reader, and both camera publishes want
this mic, so `dsnoop` does the sharing. The INMP441 puts 24-bit samples in
32-bit I²S frames, so `sox` RMS can look quiet while speech and claps are still
audible.

GPIO after the overlay: GPIO18=`PCM_CLK`, GPIO19=`PCM_FS`, GPIO20=`PCM_DIN`.
`dtparam=audio=on` coexisted with I²S on this Pi 4.

First bring-up recordings were **digital silence** (arecord meter 00%, all-zero
WAV on both I²S slots). Overlay and clocks are up; check 3.3 V, GND, SD on pin
38, and that the mic is the INMP441 (not a PDM part) before flipping L/R.

## Tests

On the Pi, after staging this repo with `deploy.sh`:

```bash
cd /home/shawn/owlcam/deploy
./pi/scripts/test_microphone.sh
./pi/scripts/test_microphone.sh --duration 30
python3 ./pi/scripts/capture_audio.py \
  --duration 10 \
  --output ~/owlcam/audio_tests/python_test.wav
```

Recordings stay in `~/owlcam/audio_tests/` (`mic_test_YYYYMMDD_HHMMSS.wav`).
The scripts do not delete them. PASS means a non-zero, non-clipped WAV;
listen to a file on the laptop if the Pi has no speaker.

## Live audio on the page

Both publishes carry the nest mic, so either camera view is one synchronised
H.264 + AAC stream:

```text
rpicam-vid ──┐                                    ┌─ /owl
             ├─ ffmpeg ─ RTSP ─ MediaMTX ─ HLS ───┤
  USB cam ───┤                                    └─ /owl2
owlmic ──────┘ (dsnoop, one mic, two readers)
```

`-use_wallclock_as_timestamps 1` puts both tracks on one clock. Without it the
demuxed HLS renditions disagree on start time and hls.js shows a black frame.

The device is probed with `arecord` before ffmpeg opens it. A missing or busy
microphone logs `publishing video only` and the video feed continues — the mic
must never be able to take the live stream down.

The live page has a level meter but no Listen button: the video element's own
speaker control is the mute switch, and `audio.js` watches `volumechange`.
Unmuting is a user gesture, which is what the Web Audio meter needs to start,
so the extra button bought nothing.

### Preview it on a laptop

MediaMTX binds to loopback, so local preview tunnels the stream and proxies it
under the same origin as the page:

```bash
make web-build
OWLCAM_SSH_IDENTITY=~/.ssh/owlcam_pi ./web/preview/serve-live.sh
# http://127.0.0.1:8770/
./web/preview/serve-live.sh --stop
```

## Do not

- Guess a different overlay if this one is present in `/boot/firmware/overlays`.
- Overwrite camera or BME280 `config.txt` lines.
- Mux the mic into MediaMTX / MP4 until standalone WAVs are proven.
