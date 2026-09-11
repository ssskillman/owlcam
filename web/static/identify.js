(() => {
  const form = document.querySelector("#identify-form")
  const fileInput = document.querySelector("#identify-files")
  const drop = document.querySelector("#identify-drop")
  const browse = document.querySelector("#identify-browse")
  const thumbs = document.querySelector("#identify-thumbs")
  const submit = document.querySelector("#identify-submit")
  const status = document.querySelector("#identify-status")
  const loader = document.querySelector("#identify-loader")
  const results = document.querySelector("#identify-results")
  const summary = document.querySelector("#identify-summary")
  const summaryTotal = document.querySelector("#identify-summary-total")
  const summaryTotalLabel = document.querySelector("#identify-summary-total-label")
  const chart = document.querySelector("#identify-chart")
  const MAX_FILES = 5
  const MAX_BYTES = 10 * 1024 * 1024
  const ACCEPT = ["image/jpeg", "image/png", "image/webp"]
  const OFFLINE_MESSAGE =
    "The photo-processing server is offline. Try again later."

  if (!form || !fileInput || !thumbs) return

  const origin = (form.dataset.apiOrigin || "").replace(/\/$/, "")
  let selected = []

  const track = (name, params) => {
    window.owlcamTrack?.(name, params)
  }

  const setStatus = (message) => {
    status.textContent = message
  }

  const apiUrl = (path) => `${origin}${path}`

  const refreshThumbs = () => {
    thumbs.replaceChildren()
    selected.forEach((file, index) => {
      const item = document.createElement("li")
      const img = document.createElement("img")
      img.alt = file.name
      img.src = URL.createObjectURL(file)
      const name = document.createElement("span")
      name.textContent = file.name
      const remove = document.createElement("button")
      remove.type = "button"
      remove.className = "identify-quiet"
      remove.textContent = "Remove"
      remove.setAttribute("aria-label", `Remove ${file.name}`)
      remove.addEventListener("click", () => {
        selected.splice(index, 1)
        refreshThumbs()
      })
      item.append(img, name, remove)
      thumbs.append(item)
    })
    submit.disabled = selected.length === 0 || !origin
  }

  const addFiles = (fileList) => {
    for (const file of fileList) {
      if (selected.length >= MAX_FILES) {
        setStatus("You can send up to 5 photos at a time.")
        break
      }
      const typeOk = ACCEPT.includes(file.type) || /\.(jpe?g|png|webp)$/i.test(file.name)
      if (!typeOk) {
        setStatus("Use JPG, PNG, or WebP photos.")
        continue
      }
      if (file.size > MAX_BYTES) {
        setStatus("Each photo must be 10 MB or smaller.")
        continue
      }
      selected.push(file)
    }
    refreshThumbs()
  }

  const sourceLabel = (value) => {
    if (value === "crop") return "Crop of the largest animal"
    if (value === "whole_image") return "The whole photo"
    return "Unavailable"
  }

  const percent = (value) => `${Math.round(Number(value) * 100)}% match`

  // Anything that rounds to 0% is not a possibility worth printing.
  const ALTERNATIVE_FLOOR = 0.005
  const CATEGORY_LABELS = {
    amphibian: "Amphibians",
    bird: "Birds",
    fish: "Fish",
    invertebrate: "Invertebrates",
    mammal: "Mammals",
    reptile: "Reptiles",
  }

  const nameLabel = (value) =>
    String(value || "")
      .split(" ")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ")

  const renderCard = (item, jobOrigin) => {
    const card = document.createElement("article")
    card.className = "identify-card"
    if (item.error) {
      const title = document.createElement("h2")
      title.textContent = item.file_name || "Photo"
      const message = document.createElement("p")
      message.textContent =
        "We couldn't analyze this photo right now. Please try again in a moment."
      card.append(title, message)
      return card
    }

    const img = document.createElement("img")
    img.alt = item.file_name || "Uploaded wildlife photo"
    if (item.annotated_image_url) {
      img.src = item.annotated_image_url.startsWith("http")
        ? item.annotated_image_url
        : `${jobOrigin}${item.annotated_image_url}`
    }
    const heading = document.createElement("h2")
    heading.textContent = item.display_name
    const score = document.createElement("p")
    score.className = "identify-score"
    score.textContent = item.is_unknown
      ? `We could not identify this one confidently. Our closest match was ${item.best_candidate || "unknown"} at ${Math.round(Number(item.confidence) * 100)}%. Try a clearer or closer photo.`
      : percent(item.confidence)
    const alts = document.createElement("p")
    alts.className = "identify-score"
    const worthShowing = (item.alternatives || []).filter(
      (row) => Number(row.confidence) >= ALTERNATIVE_FLOOR,
    )
    if (worthShowing.length) {
      alts.textContent = `Other possibilities: ${worthShowing
        .map((row) => `${row.species} ${Math.round(row.confidence * 100)}%`)
        .join(", ")}`
    } else {
      alts.hidden = true
    }
    const decided = document.createElement("p")
    decided.className = "identify-score"
    // The whole photo is the default, so naming it on every card says nothing.
    if (item.selected_source === "crop") {
      decided.textContent = `Identified from a ${sourceLabel(item.selected_source).toLowerCase()}`
    } else {
      decided.hidden = true
    }
    const disclaimer = document.createElement("p")
    disclaimer.className = "identify-disclaimer"
    disclaimer.textContent =
      "Identification is generated by an AI wildlife model and may be incorrect."

    const right = document.createElement("button")
    right.type = "button"
    right.textContent = "Looks right"
    const wrong = document.createElement("button")
    wrong.type = "button"
    wrong.textContent = "Not quite"
    // Matched on purpose: making one of them the primary action would push
    // people toward that answer, and the answer is the data we want.
    right.className = wrong.className = "identify-quiet"
    const actions = document.createElement("div")
    actions.className = "identify-feedback"
    actions.append(right, wrong)

    const extra = document.createElement("div")
    extra.hidden = true
    extra.className = "identify-correction"
    const label = document.createElement("label")
    label.textContent = "What do you think it is?"
    const input = document.createElement("input")
    input.type = "text"
    input.setAttribute("list", "identify-species")
    const unknown = document.createElement("button")
    unknown.type = "button"
    unknown.className = "identify-quiet"
    unknown.textContent = "I don't know"
    const note = document.createElement("textarea")
    note.rows = 2
    note.placeholder = "Optional note"
    const opt = document.createElement("label")
    const check = document.createElement("input")
    check.type = "checkbox"
    opt.append(check, document.createTextNode(" It's OK to use this photo to improve OwlCam."))
    const send = document.createElement("button")
    send.type = "button"
    send.textContent = "Send feedback"
    extra.append(label, input, unknown, note, opt, send)

    const sendFeedback = async (looksRight, correction, iDontKnow) => {
      try {
        await fetch(apiUrl("/api/animal-identification/feedback"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            file_name: item.file_name,
            classification: item.classification,
            looks_right: looksRight,
            correction,
            note: note.value || null,
            i_dont_know: Boolean(iDontKnow),
            train_opt_in: check.checked,
            model_version: item.model_version,
          }),
        })
        track(
          looksRight ? "animal_id_feedback_correct" : "animal_id_feedback_incorrect",
          { known: item.is_unknown ? "unknown" : "known" },
        )
        setStatus("Thanks — that helps.")
      } catch {
        setStatus("We couldn't save that feedback just now.")
      }
    }

    right.addEventListener("click", () => sendFeedback(true))
    wrong.addEventListener("click", () => {
      extra.hidden = false
    })
    unknown.addEventListener("click", () => sendFeedback(false, null, true))
    send.addEventListener("click", () => sendFeedback(false, input.value || null, false))

    card.append(img, heading, score, alts, decided, disclaimer, actions, extra)
    return card
  }

  const loadSpecies = async () => {
    if (!origin) return
    try {
      const response = await fetch(apiUrl("/api/animal-identification/species"))
      if (!response.ok) return
      const payload = await response.json()
      let list = document.querySelector("#identify-species")
      if (!list) {
        list = document.createElement("datalist")
        list.id = "identify-species"
        form.append(list)
      }
      list.replaceChildren()
      for (const name of payload.species || []) {
        const option = document.createElement("option")
        option.value = name
        list.append(option)
      }
    } catch {
      // Species hints are optional.
    }
  }

  const renderSummary = (payload) => {
    const total = Number(payload?.total)
    const categories = Array.isArray(payload?.categories) ? payload.categories : []
    if (!summary || !summaryTotal || !summaryTotalLabel || !chart || total <= 0) {
      if (summary) summary.hidden = true
      return
    }

    summaryTotal.textContent = String(total)
    summaryTotalLabel.textContent =
      total === 1 ? " animal identified so far" : " animals identified so far"
    chart.replaceChildren()

    const maximum = Math.max(
      1,
      ...categories.map((row) => Number(row?.count) || 0),
    )
    for (const row of categories) {
      const category = String(row?.category || "")
      const count = Number(row?.count) || 0
      const label = CATEGORY_LABELS[category] || nameLabel(category)
      if (!label || count <= 0 || !Array.isArray(row?.species)) continue

      const group = document.createElement("details")
      const heading = document.createElement("summary")
      const name = document.createElement("span")
      name.textContent = label
      const bar = document.createElement("progress")
      bar.max = maximum
      bar.value = count
      bar.textContent = `${count} of ${maximum}`
      bar.setAttribute("aria-label", `${label}: ${count}`)
      const amount = document.createElement("strong")
      amount.textContent = String(count)
      heading.append(name, bar, amount)

      const species = document.createElement("ul")
      species.className = "identify-species-counts"
      for (const item of row.species) {
        const itemCount = Number(item?.count) || 0
        if (!item?.species || itemCount <= 0) continue
        const line = document.createElement("li")
        const speciesName = document.createElement("span")
        speciesName.textContent = nameLabel(item.species)
        const speciesCount = document.createElement("strong")
        speciesCount.textContent = String(itemCount)
        line.append(speciesName, speciesCount)
        species.append(line)
      }
      group.append(heading, species)
      chart.append(group)
    }
    summary.hidden = chart.children.length === 0
  }

  const loadSummary = async () => {
    try {
      const response = await fetch(apiUrl("/api/animal-identification/summary"))
      if (!response.ok) return
      renderSummary(await response.json())
    } catch {
      // Identification results remain useful when the optional chart fails.
    }
  }

  browse?.addEventListener("click", () => fileInput.click())
  drop?.addEventListener("click", () => fileInput.click())
  drop?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      fileInput.click()
    }
  })
  drop?.addEventListener("dragover", (event) => {
    event.preventDefault()
    drop.classList.add("is-over")
  })
  drop?.addEventListener("dragleave", () => drop.classList.remove("is-over"))
  drop?.addEventListener("drop", (event) => {
    event.preventDefault()
    drop.classList.remove("is-over")
    addFiles(event.dataTransfer.files)
  })
  fileInput.addEventListener("change", () => {
    addFiles(fileInput.files)
    fileInput.value = ""
  })

  form.addEventListener("submit", async (event) => {
    event.preventDefault()
    results.replaceChildren()
    if (!origin) {
      setStatus(OFFLINE_MESSAGE)
      return
    }
    if (!selected.length) {
      setStatus("Add at least one photo.")
      return
    }
    track("animal_id_upload_started", { file_count: selected.length })
    setStatus("Analyzing photos…")
    if (loader) loader.hidden = false
    submit.disabled = true
    const started = performance.now()
    const body = new FormData()
    for (const file of selected) body.append("images", file, file.name)
    try {
      const response = await fetch(apiUrl("/api/animal-identification"), {
        method: "POST",
        body,
      })
      const payload = await response.json()
      if (!response.ok) {
        if (response.status < 500) {
          setStatus(payload.detail || "We couldn't accept those photos.")
          return
        }
        throw new Error("photo-processing server unavailable")
      }
      const duration = Math.round(performance.now() - started)
      for (const item of payload.results || []) {
        results.append(renderCard(item, origin))
        if (item.is_unknown) track("animal_id_unknown_returned", {})
      }
      await loadSummary()
      track("animal_id_completed", {
        file_count: (payload.results || []).length,
        processing_duration: duration,
      })
      setStatus("Identification complete.")
    } catch {
      track("animal_id_failed", { file_count: selected.length })
      setStatus(OFFLINE_MESSAGE)
    } finally {
      if (loader) loader.hidden = true
      submit.disabled = selected.length === 0
    }
  })

  if (!origin) {
    setStatus(OFFLINE_MESSAGE)
    submit.disabled = true
  } else {
    loadSpecies()
  }
  refreshThumbs()
})()
