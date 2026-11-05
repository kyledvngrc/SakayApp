// Live trip tracking (pure functions, no React, no GPS).
//
// Given a planned trip and a stream of GPS fixes, work out which step the
// commuter is on, how far they are from the end of it, and when to alert:
//   ride:  "Get off in 400 m" -> at SOON_M "Get off soon, say para" -> at HERE_M "Get off here"
//   walk:  distance to where to catch the next route, or to the destination
// Distances only, never times: waiting and traffic vary too much.
//
// Self-contained (type-only imports) so `node --test` can run it directly.
import type { LatLng, RideSegment, Segment, Trip } from './types';

export const LIVE = {
  SOON_M: 200,        // "get off soon, say para"
  HERE_M: 40,         // "get off here"
  RIDE_DONE_M: 15,    // the ride step is over
  BOARD_M: 40,        // close enough to the place to catch the route
  ON_LINE_M: 35,      // on the next route's line and moving along it: you're riding
  ARRIVE_M: 30,       // at the destination
  OFF_ROUTE_M: 120,   // further than this from the ride's line...
  OFF_ROUTE_FIXES: 3, // ...this many fixes in a row means off route
  MAX_ACCURACY_M: 80, // ignore fixes less accurate than this
  BACKTRACK_M: 60,    // GPS jitter allowed backwards along the line
} as const;

export type Fix = LatLng & { accuracy?: number | null };

export type LiveState = {
  step: number;      // index into trip.segments
  along: number;     // metres along the current ride's line (rides only)
  remaining: number; // metres to the end of the current step
  offset: number;    // metres from the current ride's line (rides only)
  offRouteFixes: number;
  offRoute: boolean;
  soonAlerted: boolean;
  hereAlerted: boolean;
  arrived: boolean;
  weakGps: boolean;
};

export type LiveEvent =
  | { type: 'get-off-soon'; step: number }
  | { type: 'get-off-here'; step: number }
  | { type: 'step'; step: number } // moved on to this step
  | { type: 'arrived' }
  | { type: 'off-route' }
  | { type: 'back-on-route' };

// ------------------------------------------------------------------ geometry

const R = 6371000;
const rad = (d: number) => (d * Math.PI) / 180;

export function distanceM(a: LatLng, b: LatLng): number {
  const h =
    Math.sin(rad(b.lat - a.lat) / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lng - a.lng) / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export function cumulative(path: LatLng[]): number[] {
  return path.reduce<number[]>((acc, p, i) => [...acc, i === 0 ? 0 : acc[i - 1] + distanceM(path[i - 1], p)], []);
}

/** Closest point on `path` to p at or after `minAlong` metres: {along, offset}. */
export function projectOnPath(path: LatLng[], cum: number[], p: LatLng, minAlong = 0): { along: number; offset: number } {
  if (path.length < 2) return { along: 0, offset: path.length ? distanceM(path[0], p) : Infinity };
  let best = { along: 0, offset: Infinity };
  for (let i = 0; i < path.length - 1; i++) {
    if (cum[i + 1] < minAlong) continue;
    const a = path[i];
    const b = path[i + 1];
    const kx = R * Math.cos(rad(a.lat));
    const bx = rad(b.lng - a.lng) * kx;
    const by = rad(b.lat - a.lat) * R;
    const px = rad(p.lng - a.lng) * kx;
    const py = rad(p.lat - a.lat) * R;
    const len2 = bx * bx + by * by;
    const segLen = cum[i + 1] - cum[i];
    let t = len2 === 0 ? 0 : Math.max(0, Math.min(1, (px * bx + py * by) / len2));
    if (cum[i] + t * segLen < minAlong && segLen > 0) t = (minAlong - cum[i]) / segLen;
    const offset = Math.hypot(px - t * bx, py - t * by);
    if (offset < best.offset) best = { along: cum[i] + t * segLen, offset };
  }
  return best;
}

// ------------------------------------------------------------------ steps

const isRide = (s: Segment | undefined): s is RideSegment => s?.kind === 'ride';

/** Where the current step ends. */
function stepTarget(seg: Segment): LatLng {
  return isRide(seg) ? { lat: seg.alight.lat, lng: seg.alight.lng } : seg.path[seg.path.length - 1];
}

const lengthCache = new WeakMap<Segment, number[]>();
function cumFor(seg: Segment): number[] {
  let cum = lengthCache.get(seg);
  if (!cum) {
    cum = cumulative(seg.path);
    lengthCache.set(seg, cum);
  }
  return cum;
}

function freshStep(trip: Trip, step: number): LiveState {
  const seg = trip.segments[step];
  const cum = cumFor(seg);
  return {
    step,
    along: 0,
    remaining: cum[cum.length - 1] ?? 0,
    offset: 0,
    offRouteFixes: 0,
    offRoute: false,
    soonAlerted: false,
    hereAlerted: false,
    arrived: false,
    weakGps: false,
  };
}

export function startTrip(trip: Trip): LiveState {
  return freshStep(trip, 0);
}

/** Move to the next step by hand (or because the commuter reached it). */
export function nextStep(trip: Trip, state: LiveState): LiveState {
  if (state.step >= trip.segments.length - 1) return { ...state, arrived: true, remaining: 0 };
  return freshStep(trip, state.step + 1);
}

export function previousStep(trip: Trip, state: LiveState): LiveState {
  return freshStep(trip, Math.max(0, state.step - 1));
}

/** Apply one GPS fix. Returns the new state and what happened. */
export function update(trip: Trip, state: LiveState, fix: Fix): { state: LiveState; events: LiveEvent[] } {
  if (state.arrived) return { state, events: [] };
  if (fix.accuracy != null && fix.accuracy > LIVE.MAX_ACCURACY_M) {
    return { state: { ...state, weakGps: true }, events: [] };
  }
  const seg = trip.segments[state.step];
  const last = state.step === trip.segments.length - 1;
  const events: LiveEvent[] = [];
  const advance = (s: LiveState): { state: LiveState; events: LiveEvent[] } => {
    const next = nextStep(trip, s);
    events.push(next.arrived ? { type: 'arrived' } : { type: 'step', step: next.step });
    return { state: next, events };
  };

  if (isRide(seg)) {
    const cum = cumFor(seg);
    const total = cum[cum.length - 1];
    const proj = projectOnPath(seg.path, cum, fix, Math.max(0, state.along - LIVE.BACKTRACK_M));
    const off = proj.offset > LIVE.OFF_ROUTE_M;
    const offRouteFixes = off ? state.offRouteFixes + 1 : 0;
    const offRoute = offRouteFixes >= LIVE.OFF_ROUTE_FIXES;
    if (offRoute && !state.offRoute) events.push({ type: 'off-route' });
    if (!offRoute && state.offRoute) events.push({ type: 'back-on-route' });
    // Only trust progress along the line while near it.
    const along = off ? state.along : Math.max(state.along, proj.along);
    const remaining = Math.max(0, total - along);
    let next: LiveState = { ...state, along, remaining, offset: proj.offset, offRouteFixes, offRoute, weakGps: false };
    if (!off && remaining <= LIVE.SOON_M && !next.soonAlerted) {
      next = { ...next, soonAlerted: true };
      if (remaining > LIVE.HERE_M) events.push({ type: 'get-off-soon', step: state.step });
    }
    if (!off && remaining <= LIVE.HERE_M && !next.hereAlerted) {
      next = { ...next, hereAlerted: true };
      events.push({ type: 'get-off-here', step: state.step });
    }
    if (!off && remaining <= LIVE.RIDE_DONE_M) return advance(next);
    return { state: next, events };
  }

  // Walking: to the next route, or to the destination.
  const remaining = distanceM(fix, stepTarget(seg));
  const next: LiveState = { ...state, remaining, weakGps: false };
  if (last && remaining <= LIVE.ARRIVE_M) return advance(next);
  const following = trip.segments[state.step + 1];
  if (!last && remaining <= LIVE.BOARD_M) return advance(next);
  if (isRide(following)) {
    // Already riding it (boarded a little before or after the planned spot)?
    const cum = cumFor(following);
    const p = projectOnPath(following.path, cum, fix);
    if (p.offset <= LIVE.ON_LINE_M && p.along >= LIVE.BOARD_M * 2 && p.along < cum[cum.length - 1] - LIVE.SOON_M) {
      const boarded = advance(next);
      const riding = update(trip, boarded.state, fix); // count progress on the ride from this fix
      return { state: riding.state, events: [...boarded.events, ...riding.events] };
    }
  }
  return { state: next, events };
}

// ------------------------------------------------------------------ wording

/** 'Get off in 400 m', '120 m to the Maa - Agdao route', ... */
export function headline(trip: Trip, state: LiveState, distanceText: (m: number) => string): string {
  if (state.arrived) return 'You have arrived';
  const seg = trip.segments[state.step];
  if (isRide(seg)) {
    if (state.hereAlerted) return 'Get off here';
    if (state.soonAlerted) return 'Get off soon, say “para”';
    return `Get off in ${distanceText(state.remaining)}`;
  }
  const following = trip.segments[state.step + 1];
  if (isRide(following)) return `${distanceText(state.remaining)} to the ${following.route.name} route`;
  return `${distanceText(state.remaining)} to your destination`;
}

/** What to say out loud for an event, or null. */
export function spoken(trip: Trip, event: LiveEvent): string | null {
  switch (event.type) {
    case 'get-off-soon':
      return 'Get off soon. Say para.';
    case 'get-off-here':
      return 'Get off here.';
    case 'arrived':
      return 'You have arrived.';
    case 'off-route':
      return 'You seem to be off the route.';
    case 'step': {
      const seg = trip.segments[event.step];
      if (isRide(seg)) return `Ride ${seg.route.name}.`;
      const following = trip.segments[event.step + 1];
      return isRide(following) ? `Walk to the ${following.route.name} route.` : 'Walk to your destination.';
    }
    default:
      return null;
  }
}
