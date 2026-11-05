// Geometry helpers for the admin page (pure functions; mirrors backend/app/geo.py).
// Points are {lat, lng}.
const Geo = (() => {
  const R = 6371000;
  const rad = (d) => (d * Math.PI) / 180;

  const dist = (a, b) => {
    const p1 = rad(a.lat), p2 = rad(b.lat);
    const h = Math.sin((p2 - p1) / 2) ** 2 +
      Math.cos(p1) * Math.cos(p2) * Math.sin(rad(b.lng - a.lng) / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  };

  const localXY = (o, p) => [
    rad(p.lng - o.lng) * R * Math.cos(rad(o.lat)),
    rad(p.lat - o.lat) * R,
  ];

  const segments = (path) => path.slice(1).map((b, i) => [path[i], b]);

  const pathLength = (path) => segments(path).reduce((sum, [a, b]) => sum + dist(a, b), 0);

  // Metres along `path` to the point closest to p, and how far p is from the path.
  const positionAlong = (path, p) => {
    if (path.length < 2) return { along: 0, offset: path.length ? dist(path[0], p) : Infinity };
    let start = 0;
    return segments(path).reduce((best, [a, b]) => {
      const [bx, by] = localXY(a, b);
      const [px, py] = localXY(a, p);
      const len2 = bx * bx + by * by;
      const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, (px * bx + py * by) / len2));
      const offset = Math.hypot(px - t * bx, py - t * by);
      const segLen = dist(a, b);
      const candidate = { along: start + t * segLen, offset };
      start += segLen;
      return offset < best.offset ? candidate : best;
    }, { along: 0, offset: Infinity });
  };

  // The point `d` metres along `path`.
  const pointAt = (path, d) => {
    let remaining = d;
    for (const [a, b] of segments(path)) {
      const len = dist(a, b);
      if (remaining <= len) {
        const t = len === 0 ? 0 : remaining / len;
        return { lat: a.lat + t * (b.lat - a.lat), lng: a.lng + t * (b.lng - a.lng) };
      }
      remaining -= len;
    }
    return path[path.length - 1];
  };

  // Points every `spacing` metres along the path, always including both ends.
  const pointsEvery = (path, spacing) => {
    const total = pathLength(path);
    const count = Math.max(1, Math.round(total / spacing));
    return Array.from({ length: count + 1 }, (_, i) => pointAt(path, (total * i) / count));
  };

  return { dist, pathLength, positionAlong, pointAt, pointsEvery };
})();
