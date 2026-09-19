# Pi configuration

The live Pi must supply these files before Phase 0 is complete:

- `mediamtx.yml`: reviewed copy of `/etc/mediamtx.yml`
- `mediamtx.paths-owl.yml`: optional `paths:` snippet for `owl` and `owl2`
- `mediamtx.version`: exact output of `mediamtx --version`, such as `v1.20.1`

Do not invent either value while the Pi is offline. Scan the YAML for
credentials, tokens, keys, and access-control users before committing it.
