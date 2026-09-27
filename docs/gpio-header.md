# GPIO 40-pin header — OwlCam nest box

Ground truth for the admin **GPIO & nest hardware** panel. Edit
[`web/data/gpio_header.json`](../web/data/gpio_header.json) when the harness
changes, then rebuild and deploy the site.

The panel shows [`web/static/owlcam-gpio-wiring.svg`](../web/static/owlcam-gpio-wiring.svg)
plus callouts from `wiringDiagram` in the JSON. Replace that SVG with a field
photo (same filename or update `wiringDiagram.image`) if you want a bench
picture instead of the schematic.

## Header (13 positions)

| Phys | BCM | Signal | Lands on | Pi job |
| ---: | --- | --- | --- | --- |
| 1 | — | 3.3 V | INMP441, BME280 | Sensor power |
| 2 | — | 5 V | LM2596 IN+ | Buck input for IR rail |
| 3 | 2 | SDA | BME280 | Climate on `/diagnostics` |
| 5 | 3 | SCL | BME280 | I²C clock |
| 6 | — | GND | Mic, BME, L/R | Common ground |
| 9 | — | GND | Harness | Extra ground strap |
| 12 | 18 | PCM_CLK | INMP441 SCK | Live nest audio (I²S) |
| 14 | — | GND | MOSFET module | IR switch return |
| 16 | 23 | OUT | MOSFET SIG | IR illuminator (`owlcam-ir`) |
| 20 | — | GND | LM2596 IN− | Buck input return |
| 35 | 19 | PCM_FS | INMP441 WS | I²S frame sync |
| 38 | 20 | PCM_DIN | INMP441 SD | I²S data |
| 39 | — | GND | Harness | Bundle return |

## Not on the GPIO header

- **CSI** — IMX708 → `/owl`
- **USB** — UVC camera → `/owl2`

See also [`microphone.md`](microphone.md), [`live-feed.md`](live-feed.md), and the
IR handoff for MOSFET / LM2596 wiring.
