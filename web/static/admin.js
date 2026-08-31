(() => {
  const API = "/admin/api"
  const dialog = document.querySelector("#admin-dialog")
  const openButton = document.querySelector("#admin-open")
  const closeButton = document.querySelector("#admin-close")
  const login = document.querySelector("#admin-login")
  const loginForm = document.querySelector("#admin-login-form")
  const loginStatus = document.querySelector("#admin-login-status")
  const dashboard = document.querySelector("#admin-dashboard")
  const overallStatus = document.querySelector("#admin-overall-status")
  const streamState = document.querySelector("#admin-stream-state")
  const streamToggle = document.querySelector("#admin-stream-toggle")
  const services = document.querySelector("#admin-services")
  const hostStatus = document.querySelector("#admin-host-status")
  const firebaseStatus = document.querySelector("#admin-firebase-status")
  const refreshButton = document.querySelector("#admin-refresh")
  const logoutButton = document.querySelector("#admin-logout")
  const logService = document.querySelector("#admin-log-service")
  const loadLogsButton = document.querySelector("#admin-load-logs")
  const logOutput = document.querySelector("#admin-log-output")
  const actionStatus = document.querySelector("#admin-action-status")

  if (!dialog || !openButton) return

  let csrfToken = null
  let streamEnabled = null
  let refreshTimer = null

  const api = async (path, options = {}) => {
    const headers = { ...(options.headers || {}) }
    if (options.body) headers["Content-Type"] = "application/json"
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    })
    let payload = {}
    try {
      payload = await response.json()
    } catch {
      throw new Error(`Admin API returned HTTP ${response.status}`)
    }
    if (!response.ok) {
      const error = new Error(payload?.error?.message || "Admin request failed")
      error.status = response.status
      throw error
    }
    return payload
  }

  const showLogin = (message = "") => {
    csrfToken = null
    login.hidden = false
    dashboard.hidden = true
    loginStatus.textContent = message
    window.clearTimeout(refreshTimer)
    refreshTimer = null
  }

  const showDashboard = () => {
    login.hidden = true
    dashboard.hidden = false
    loginStatus.textContent = ""
  }

  const formatDuration = (seconds) => {
    if (!Number.isFinite(seconds)) return "Unavailable"
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    return days ? `${days}d ${hours}h` : `${hours}h`
  }

  const replaceItems = (container, items, className) => {
    container.replaceChildren()
    for (const [label, value, state] of items) {
      const item = document.createElement("div")
      item.className = className
      if (state) item.dataset.state = state
      const key = document.createElement("span")
      key.textContent = label
      const result = document.createElement("strong")
      result.textContent = value
      item.append(key, result)
      container.append(item)
    }
  }

  const renderStatus = (payload) => {
    csrfToken = payload.csrfToken
    streamEnabled = Boolean(payload.stream?.isEnabled)
    overallStatus.textContent = streamEnabled ? "Feed online" : "Feed offline"
    overallStatus.dataset.state = streamEnabled ? "active" : "inactive"
    streamState.textContent = streamEnabled
      ? "The camera capture unit is running."
      : "The camera capture unit is stopped."
    streamToggle.textContent = streamEnabled ? "Turn feed off" : "Turn feed on"
    streamToggle.classList.toggle("admin-danger", streamEnabled)
    streamToggle.disabled = false

    replaceItems(
      services,
      Object.entries(payload.services || {}).map(([name, state]) => [
        name,
        state,
        state,
      ]),
      "admin-service",
    )
    const host = payload.host || {}
    replaceItems(
      hostStatus,
      [
        ["Uptime", formatDuration(host.uptimeSeconds)],
        [
          "Memory free",
          Number.isFinite(host.memoryAvailableGiB)
            ? `${host.memoryAvailableGiB} GiB`
            : "Unavailable",
        ],
        [
          "Disk free",
          Number.isFinite(host.diskFreeGiB)
            ? `${host.diskFreeGiB} GiB`
            : "Unavailable",
        ],
        [
          "Load (1m)",
          Number.isFinite(host.load1) ? String(host.load1) : "Unavailable",
        ],
        ["Wi-Fi", host.wifiConnection || "Not connected"],
      ],
      "admin-metric",
    )
  }

  const loadFirebase = async () => {
    try {
      const payload = await api("/firebase")
      firebaseStatus.textContent = payload.reachable
        ? `HTTP ${payload.status} in ${payload.latencyMs} ms → ${payload.redirectTarget || "no redirect"}`
        : `Firebase did not answer (${payload.latencyMs} ms)`
      firebaseStatus.dataset.state = payload.reachable ? "active" : "inactive"
    } catch (error) {
      if (error.status === 401) return showLogin("Your session expired.")
      firebaseStatus.textContent = "Firebase edge check failed."
      firebaseStatus.dataset.state = "inactive"
    }
  }

  const refresh = async () => {
    window.clearTimeout(refreshTimer)
    actionStatus.textContent = "Refreshing…"
    try {
      const payload = await api("/status")
      showDashboard()
      renderStatus(payload)
      actionStatus.textContent = `Updated ${new Date(payload.sampledAt).toLocaleTimeString()}`
      loadFirebase()
      refreshTimer = window.setTimeout(refresh, 10000)
    } catch (error) {
      if (error.status === 401) {
        showLogin("Sign in to open field station controls.")
      } else {
        actionStatus.textContent = error.message
        refreshTimer = window.setTimeout(refresh, 10000)
      }
    }
  }

  const checkSession = async () => {
    loginStatus.textContent = "Checking session…"
    try {
      const session = await api("/session")
      if (session.authenticated) {
        csrfToken = session.csrfToken
        await refresh()
      } else {
        showLogin()
        document.querySelector("#admin-username")?.focus()
      }
    } catch {
      showLogin("The admin service is unavailable.")
    }
  }

  openButton.addEventListener("click", () => {
    dialog.showModal()
    checkSession()
  })

  closeButton.addEventListener("click", () => dialog.close())
  dialog.addEventListener("close", () => {
    window.clearTimeout(refreshTimer)
    refreshTimer = null
    openButton.focus()
  })

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault()
    const form = new FormData(loginForm)
    const submit = loginForm.querySelector("button[type=submit]")
    submit.disabled = true
    loginStatus.textContent = "Signing in…"
    try {
      const payload = await api("/session", {
        method: "POST",
        body: JSON.stringify({
          username: form.get("username"),
          password: form.get("password"),
        }),
      })
      csrfToken = payload.csrfToken
      loginForm.reset()
      document.querySelector("#admin-username").value = "admin"
      await refresh()
    } catch (error) {
      loginStatus.textContent = error.message
      document.querySelector("#admin-password")?.focus()
    } finally {
      submit.disabled = false
    }
  })

  streamToggle.addEventListener("click", async () => {
    const nextEnabled = !streamEnabled
    if (
      !nextEnabled &&
      !window.confirm("Turn off the live camera feed? The admin panel will stay available.")
    ) {
      return
    }
    streamToggle.disabled = true
    actionStatus.textContent = nextEnabled ? "Starting feed…" : "Stopping feed…"
    try {
      const payload = await api("/stream", {
        method: "POST",
        headers: { "X-Owlcam-Csrf": csrfToken },
        body: JSON.stringify({ enabled: nextEnabled }),
      })
      streamEnabled = payload.stream.isEnabled
      await refresh()
    } catch (error) {
      actionStatus.textContent = error.message
      streamToggle.disabled = false
    }
  })

  refreshButton.addEventListener("click", refresh)

  logoutButton.addEventListener("click", async () => {
    try {
      await api("/session", {
        method: "DELETE",
        headers: { "X-Owlcam-Csrf": csrfToken },
      })
    } finally {
      showLogin("Signed out.")
      document.querySelector("#admin-username")?.focus()
    }
  })

  loadLogsButton.addEventListener("click", async () => {
    loadLogsButton.disabled = true
    logOutput.textContent = "Loading journal…"
    try {
      const payload = await api(
        `/logs?service=${encodeURIComponent(logService.value)}&lines=100`,
      )
      logOutput.textContent = payload.lines.length
        ? payload.lines.join("\n")
        : "No journal lines for this service."
    } catch (error) {
      if (error.status === 401) return showLogin("Your session expired.")
      logOutput.textContent = error.message
    } finally {
      loadLogsButton.disabled = false
    }
  })
})()
