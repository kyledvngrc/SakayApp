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

  // Distance from p to the segment a-b, in metres.
  const offsetFromSegment = (a, b, p) => {
    const [bx, by] = localXY(a, b);
    const [px, py] = localXY(a, p);
    const len2 = bx * bx + by * by;
    const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, (px * bx + py * by) / len2));
    return Math.hypot(px - t * bx, py - t * by);
  };

  // Index of the segment of `path` closest to p (segment i runs from point i to i+1).
  const nearestSegment = (path, p) => segments(path)
    .map(([a, b], i) => ({ i, d: offsetFromSegment(a, b, p) }))
    .reduce((best, s) => (s.d < best.d ? s : best), { i: 0, d: Infinity }).i;

  return { dist, pathLength, nearestSegment };
})();
