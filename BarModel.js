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
    presentation: presentation,
    validPercentage: validPercentage
  }
}
