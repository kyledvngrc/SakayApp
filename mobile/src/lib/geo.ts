// Small geometry helpers (pure functions).
import type { Landmark, LatLng } from './types';

const R = 6371000;
const rad = (d: number) => (d * Math.PI) / 180;

export function distanceM(a: LatLng, b: LatLng): number {
  const h =
    Math.sin(rad(b.lat - a.lat) / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lng - a.lng) / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** The closest landmark within `maxM` metres, if any. */
export function nearestLandmark(p: LatLng, landmarks: Landmark[], maxM = 300): Landmark | undefined {
  return landmarks
    .map((l) => ({ l, d: distanceM(p, l) }))
    .filter((x) => x.d <= maxM)
    .sort((a, b) => a.d - b.d)[0]?.l;
}

/** react-native-maps uses {latitude, longitude}. */
export const toCoord = (p: LatLng) => ({ latitude: p.lat, longitude: p.lng });

export const DAVAO = { latitude: 7.0731, longitude: 125.6128, latitudeDelta: 0.08, longitudeDelta: 0.08 };
