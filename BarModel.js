function validPercentage(value) {
  return typeof value === "number" && isFinite(value)
    && value >= 0 && value <= 100
}

function batteryParts(snapshot) {
  var status = snapshot && snapshot.status
  var battery = status && status.battery
  if (!battery || typeof battery !== "object" || Array.isArray(battery)) return []

  var names = [
    { key: "left", short: "L", long: "Left" },
    { key: "right", short: "R", long: "Right" },
    { key: "case", short: "C", long: "Case" }
  ]
  var parts = []
  for (var i = 0; i < names.length; i++) {
    var name = names[i]
    var value = battery[name.key]
    if (!value || !validPercentage(value.percentage)) continue
    parts.push({
      key: name.key,
      short: name.short,
      long: name.long,
      percentage: Math.round(value.percentage),
      charging: value.charging === true
    })
  }
  return parts
}

function titleCase(value) {
  var text = String(value || "unavailable").replace(/_/g, " ")
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function ancModes(snapshot) {
  var advertised = snapshot && Array.isArray(snapshot.anc_modes)
    ? snapshot.anc_modes : []
  var labels = {
    off: "Off",
    transparency: "Transparency",
    on: "On",
    light: "Light",
    medium: "Medium",
    deep: "Deep",
    smart: "Smart"
  }
  var preferred = ["off", "transparency", "on", "light", "medium", "deep", "smart"]
  var seen = {}
  var options = []

  function append(mode) {
    var value = String(mode || "")
    if (!value || seen[value]) return
    seen[value] = true
    options.push({ value: value, label: labels[value] || titleCase(value) })
  }

  for (var i = 0; i < preferred.length; i++)
    if (advertised.indexOf(preferred[i]) !== -1) append(preferred[i])
  for (var j = 0; j < advertised.length; j++) append(advertised[j])
  return options
}

function ancGroups(snapshot) {
  var modes = ancModes(snapshot)
  var groups = [
    { title: "Noise control", options: [] },
    { title: "ANC strength", options: [] },
    { title: "Other modes", options: [] }
  ]
  for (var i = 0; i < modes.length; i++) {
    var option = modes[i]
    if (["off", "transparency", "on"].indexOf(option.value) !== -1) {
      groups[0].options.push({value: option.value,
        label: option.value === "on" ? "Noise cancellation" : option.label})
    } else if (["light", "medium", "deep", "smart"].indexOf(option.value) !== -1) {
      groups[1].options.push(option)
    } else {
      groups[2].options.push(option)
    }
  }
  return groups.filter(function(group) { return group.options.length > 0 })
}

function currentAncMode(snapshot) {
  var status = snapshot && snapshot.status
  if (!status || !status.anc) return ""
  if (status.anc === "on" && status.anc_level) return String(status.anc_level)
  return String(status.anc)
}

function eqPresets(snapshot) {
  var eq = snapshot && snapshot.eq
  return eq && Array.isArray(eq.presets) ? eq.presets : []
}

function customEqEntries(snapshot) {
  var eq = snapshot && snapshot.eq
  return eq && Array.isArray(eq.custom_entries) ? eq.custom_entries : []
}

function compatibility(snapshot) {
  var value = snapshot ? String(snapshot.compatibility || "") : ""
  if (value === "verified" || value === "community_tested") return value
  return value ? "experimental" : ""
}

function compatibilityLabel(snapshot) {
  var value = compatibility(snapshot)
  if (value === "verified") return "Verified"
  if (value === "community_tested") return "Community tested"
  if (value === "experimental") return "Experimental device"
  return ""
}

function reportActionLabel(snapshot) {
  return compatibility(snapshot) === "experimental"
    ? "Report compatibility" : "Report a problem"
}

var COMPATIBILITY_ISSUE_URL = "https://github.com/GazzasaurusRex/oneplus-buds-omarchy/issues/new?template=compatibility.md"

function safeReportModel(snapshot) {
  var status = snapshot && snapshot.status
  var model = status && status.model ? String(status.model).trim() : ""
  if (!model || model.length > 60) return ""
  if (!/^oneplus\b.*\bbuds\b/i.test(model)
      && !/^oppo\b.*\b(?:buds|enco)\b/i.test(model)) return ""
  if (!/^[A-Za-z0-9][A-Za-z0-9 .()+_-]*$/.test(model)) return ""
  if (/(?:[0-9a-f]{2}:){5}[0-9a-f]{2}/i.test(model)
      || /\b[0-9a-f]{6,}\b/i.test(model)) return ""
  return model
}

function reportFilename(snapshot, date) {
  var when = date instanceof Date && !isNaN(date.getTime()) ? date : new Date()
  var year = String(when.getFullYear()).padStart(4, "0")
  var month = String(when.getMonth() + 1).padStart(2, "0")
  var day = String(when.getDate()).padStart(2, "0")
  var model = safeReportModel(snapshot)
  var slug = model.toLowerCase().replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
  if (!slug) slug = "oneplus-buds"
  return slug + "-report-" + year + "-" + month + "-" + day + ".txt"
}

function textReportUrl(value) {
  var url = String(value || "")
  if (/\.txt$/i.test(url)) return url
  var slash = url.lastIndexOf("/")
  var dot = url.lastIndexOf(".")
  if (dot > slash) url = url.slice(0, dot)
  return url + ".txt"
}

function reportLocationLabel(fileUrl, filename, homeUrl) {
  var url = String(fileUrl || "")
  if (url.indexOf("file://") !== 0) return String(filename || "")
  try {
    var path = decodeURIComponent(url.slice(7))
    var home = String(homeUrl || "")
    if (home.indexOf("file://") === 0) home = decodeURIComponent(home.slice(7))
    if (home && (path === home || path.indexOf(home + "/") === 0))
      path = "~" + path.slice(home.length)
    return path || String(filename || "")
  } catch (_error) {
    return String(filename || "")
  }
}

function compatibilityIssueUrl(snapshot) {
  var model = safeReportModel(snapshot)
  if (!model) return COMPATIBILITY_ISSUE_URL
  return COMPATIBILITY_ISSUE_URL + "&title="
    + encodeURIComponent("[Compatibility] " + model)
}

function presentation(connection, snapshot) {
  var connected = connection === "connected"
  var parts = connected ? batteryParts(snapshot) : []
  var labels = []
  var details = []
  for (var i = 0; i < parts.length; i++) {
    var suffix = parts[i].charging ? "⚡" : ""
    labels.push(parts[i].short + " " + parts[i].percentage + "%" + suffix)
    details.push(parts[i].long + ": " + parts[i].percentage + "%"
      + (parts[i].charging ? " (charging)" : ""))
  }

  var status = snapshot && snapshot.status
  var model = status && status.model ? String(status.model) : "OnePlus earbuds"
  var tooltip = model + "\n" + titleCase(connection)
  if (details.length) tooltip += "\n" + details.join(" · ")

  return {
    connected: connected,
    icon: connected ? "󰋋" : "󰟎",
    label: labels.join("  "),
    tooltip: tooltip
  }
}

if (typeof module !== "undefined") {
  module.exports = {
    batteryParts: batteryParts,
    ancModes: ancModes,
    ancGroups: ancGroups,
    currentAncMode: currentAncMode,
    eqPresets: eqPresets,
    customEqEntries: customEqEntries,
    compatibility: compatibility,
    compatibilityLabel: compatibilityLabel,
    reportActionLabel: reportActionLabel,
    safeReportModel: safeReportModel,
    reportFilename: reportFilename,
    textReportUrl: textReportUrl,
    reportLocationLabel: reportLocationLabel,
    compatibilityIssueUrl: compatibilityIssueUrl,
    COMPATIBILITY_ISSUE_URL: COMPATIBILITY_ISSUE_URL,
    presentation: presentation,
    validPercentage: validPercentage
  }
}
