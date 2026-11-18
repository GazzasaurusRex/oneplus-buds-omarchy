function clampGain(value, minimum, maximum, step) {
  step = step > 0 ? step : 1
  var snapped = minimum + Math.round((value - minimum) / step) * step
  return Math.max(minimum, Math.min(maximum, snapped))
}

function points(gains, width, height, minimum, maximum) {
  var range = Math.max(1, maximum - minimum)
  return gains.map(function(gain, index) {
    return {x: gains.length === 1 ? width / 2 : index * width / (gains.length - 1),
      y: (maximum - Math.max(minimum, Math.min(maximum, gain))) * height / range}
  })
}

// Monotone cubic interpolation: a smooth display of the stored band gains,
// without drawing peaks or troughs beyond adjacent control points.
function segments(p) {
  if (p.length < 2) return []
  var slopes = [], tangents = [], result = []
  for (var i = 0; i < p.length - 1; i++)
    slopes.push((p[i + 1].y - p[i].y) / Math.max(0.001, p[i + 1].x - p[i].x))
  tangents.push(slopes[0])
  for (var j = 1; j < p.length - 1; j++)
    tangents.push(slopes[j - 1] * slopes[j] <= 0 ? 0
      : 2 * slopes[j - 1] * slopes[j] / (slopes[j - 1] + slopes[j]))
  tangents.push(slopes[slopes.length - 1])
  for (var k = 0; k < p.length - 1; k++) {
    var a = p[k], b = p[k + 1], dx = (b.x - a.x) / 3
    var low = Math.min(a.y, b.y), high = Math.max(a.y, b.y)
    result.push({c1: {x: a.x + dx, y: Math.max(low, Math.min(high, a.y + tangents[k] * dx))},
      c2: {x: b.x - dx, y: Math.max(low, Math.min(high, b.y - tangents[k + 1] * dx))}, end: b})
  }
  return result
}

function linePath(p) {
  if (!p.length) return ""
  var path = "M " + p[0].x + " " + p[0].y
  segments(p).forEach(function(s) {
    path += " C " + s.c1.x + " " + s.c1.y + " " + s.c2.x + " " + s.c2.y
      + " " + s.end.x + " " + s.end.y
  })
  return path
}

if (typeof module !== "undefined")
  module.exports = {clampGain: clampGain, points: points, segments: segments, linePath: linePath}
