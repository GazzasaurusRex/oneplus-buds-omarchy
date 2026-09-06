function initialState() {
  return {
    connection: "stopped",
    snapshot: null,
    lastResponse: null,
    lastError: ""
  }
}

function parseLine(line) {
  try {
    var message = JSON.parse(String(line || ""))
    if (!message || typeof message !== "object" || Array.isArray(message))
      return { ok: false, error: "Backend message must be an object" }
    if (message.schema_version !== 1)
      return { ok: false, error: "Unsupported backend schema" }
    return { ok: true, message: message }
  } catch (_error) {
    return { ok: false, error: "Invalid backend JSON" }
  }
}

function applyMessage(state, message) {
  var next = {
    connection: String(state && state.connection || "stopped"),
    snapshot: state ? state.snapshot : null,
    lastResponse: state ? state.lastResponse : null,
    lastError: String(state && state.lastError || "")
  }
  if (message.type === "connection") {
    next.connection = String(message.connection || "disconnected")
    next.lastError = message.error ? String(message.error) : ""
  } else if (message.type === "snapshot") {
    next.snapshot = message.snapshot || null
  } else if (message.type === "command_response") {
    next.lastResponse = message
    next.lastError = message.ok === false && message.error
      ? String(message.error.message || "Command failed") : ""
  }
  return next
}

if (typeof module !== "undefined") {
  module.exports = {
    initialState: initialState,
    parseLine: parseLine,
    applyMessage: applyMessage
  }
}
