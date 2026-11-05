// Live trip tracking tests (TEST DATA ONLY). Run: npm test
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { headline, LIVE, nextStep, previousStep, projectOnPath, cumulative, startTrip, update, type LiveEvent, type LiveState } from '../src/lib/live.ts';
import type { LatLng, RideSegment, Trip, WalkSegment } from '../src/lib/types.ts';

const BASE = { lat: 7.07, lng: 125.61 };
const at = (east: number, north: number): LatLng => ({
  lat: BASE.lat + north / 111_195,
  lng: BASE.lng + east / (111_195 * Math.cos((BASE.lat * Math.PI) / 180)),
});
const text = (m: number) => `${Math.round(m)} m`;

const walk = (from: LatLng, to: LatLng): WalkSegment => ({ kind: 'walk', from: '', to: '', distance_m: 0, path: [from, to], instruction: '' });
const ride = (code: string, name: string, path: LatLng[]): RideSegment => ({
  kind: 'ride',
  route: { code, name, color: '#000000', vehicle_type: 'jeepney' },
  heading: null,
  board: { ...path[0], along_m: 0, place: { kind: 'none', name: null } },
  alight: { ...path[path.length - 1], along_m: 0, place: { kind: 'none', name: null } },
  distance_km: 0,
  fare: null,
  path,
  instruction: '',
});

// Walk 100 m north to NS, ride NS 2 km north, walk 100 m east to EW, ride EW 1 km east, walk 50 m north.
const TRIP: Trip = {
  route_codes: ['NS', 'EW'], transfers: 1, ride_km: 3, walking_m: 250, total_fare: null, fare_available: false,
  segments: [
    walk(at(0, -100), at(0, 0)),
    ride('NS', 'Plaza - Market', [at(0, 0), at(0, 1000), at(0, 2000)]),
    walk(at(0, 2000), at(100, 2000)),
    ride('EW', 'West - East', [at(100, 2000), at(1100, 2000)]),
    walk(at(1100, 2000), at(1100, 2050)),
  ],
};

function drive(points: LatLng[], state = startTrip(TRIP)) {
  const events: LiveEvent[] = [];
  for (const p of points) {
    const r = update(TRIP, state, p);
    state = r.state;
    events.push(...r.events);
  }
  return { state, events };
}
const northAlong = (from: number, to: number, step = 50) =>
  Array.from({ length: Math.floor((to - from) / step) + 1 }, (_, i) => at(0, from + i * step));

test('projection finds position along the line', () => {
  const path = [at(0, 0), at(0, 1000), at(1000, 1000)];
  const p = projectOnPath(path, cumulative(path), at(30, 500));
  assert.ok(Math.abs(p.along - 500) < 2 && Math.abs(p.offset - 30) < 2);
  const later = projectOnPath(path, cumulative(path), at(0, 500), 1200);
  assert.ok(later.along >= 1199, 'never goes back before minAlong');
});

test('walking to the first route, then boarding', () => {
  const { state, events } = drive([at(0, -100), at(0, -50), at(0, -20)]);
  assert.equal(state.step, 1);
  assert.deepEqual(events, [{ type: 'step', step: 1 }]);
  assert.equal(headline(TRIP, state, text), 'Get off in 2000 m');
});

test('ride alerts: soon, then here, then the next step', () => {
  const onRide = nextStep(TRIP, startTrip(TRIP));
  const { state, events } = drive(northAlong(0, 2000), onRide);
  const types = events.map((e) => e.type);
  assert.deepEqual(types, ['get-off-soon', 'get-off-here', 'step']);
  assert.equal(state.step, 2);
  assert.equal(headline(TRIP, state, text), '100 m to the West - East route');
});

test('remaining distance counts down along the ride', () => {
  const onRide = nextStep(TRIP, startTrip(TRIP));
  const { state } = drive([at(5, 300), at(-5, 700)], onRide);
  assert.ok(Math.abs(state.remaining - 1300) < 3);
  assert.equal(headline(TRIP, state, text), 'Get off in 1300 m');
});

test('GPS jitter backwards does not undo progress', () => {
  const onRide = nextStep(TRIP, startTrip(TRIP));
  const { state } = drive([at(0, 900), at(0, 860)], onRide);
  assert.ok(Math.abs(state.along - 900) < 2);
});

test('inaccurate fixes are ignored', () => {
  const onRide = nextStep(TRIP, startTrip(TRIP));
  const r = update(TRIP, onRide, { ...at(0, 1900), accuracy: LIVE.MAX_ACCURACY_M + 50 });
  assert.equal(r.state.along, 0);
  assert.equal(r.state.weakGps, true);
  assert.deepEqual(r.events, []);
});

test('off route after several fixes far from the line, and back again', () => {
  const onRide = nextStep(TRIP, startTrip(TRIP));
  const away = [at(300, 500), at(310, 520), at(320, 540)];
  const off = drive(away, onRide);
  assert.equal(off.state.offRoute, true);
  assert.deepEqual(off.events.map((e) => e.type), ['off-route']);
  assert.equal(off.state.along, 0, 'no progress counted while off the line');
  const back = drive([at(0, 600)], off.state);
  assert.deepEqual(back.events.map((e) => e.type), ['back-on-route']);
});

test('boarding a bit past the planned spot is detected', () => {
  const { state, events } = drive([at(0, -100), at(0, 150), at(0, 200)]);
  assert.equal(state.step, 1);
  assert.equal(events[0].type, 'step');
  assert.ok(state.along >= 195);
});

test('arrives at the destination', () => {
  let s: LiveState = startTrip(TRIP);
  for (let i = 0; i < 4; i++) s = nextStep(TRIP, s);
  const { state, events } = drive([at(1100, 2010), at(1100, 2040)], s);
  assert.equal(state.arrived, true);
  assert.deepEqual(events.map((e) => e.type), ['arrived']);
  assert.equal(headline(TRIP, state, text), 'You have arrived');
});

test('manual next and back', () => {
  const s = nextStep(TRIP, startTrip(TRIP));
  assert.equal(s.step, 1);
  assert.equal(previousStep(TRIP, s).step, 0);
  assert.equal(previousStep(TRIP, startTrip(TRIP)).step, 0);
});
