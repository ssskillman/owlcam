# UI previews (local)

Design explorations for the live home page and nest save counter. Grounded in the
existing OwlCam tokens (night / moss / amber) and **ui-ux-pro-max** guidance:
subtle status copy, tabular numerals, `aria-live` with atomic context, no loud
badges, `prefers-reduced-motion` for the live dot.

## Full home (3 versions)

```bash
cd web && ./preview/serve-previews.sh
```

| Port | URL | Idea |
|------|-----|------|
| 8771 | `/preview/full-a-whisper-rail.html` | **Production direction** — dot + muted “**7** nest saves · 24h” |
| 8772 | `/preview/full-b-inline-stat.html` | Plain text in the nav, no chrome |
| 8773 | `/preview/full-c-ledger-chip.html` | Uppercase ledger with amber underline |

Single server alternative:

```bash
cd web && python3 -m http.server 8771
```

## Legacy header-only mocks

- `v1-console-chip.html`
- `v2-telemetry-rail.html`
