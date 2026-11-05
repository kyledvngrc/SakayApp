// HTTP client for the SakayApp back-end.
import Constants from 'expo-constants';

import type { Landmark, LatLng, NearbyRoute, PlanResponse, RiderType, RouteInfo } from './types';

/**
 * EXPO_PUBLIC_API_URL wins (e.g. http://192.168.1.20:8000). Otherwise use the
 * computer running the Expo dev server, which also runs the back-end on :8000.
 */
function resolveBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL;
  if (fromEnv) return fromEnv.replace(/\/$/, '');
  const host = Constants.expoConfig?.hostUri?.split(':')[0];
  return `http://${host ?? 'localhost'}:8000`;
}

export const API_URL = resolveBaseUrl();

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_URL + path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
  } catch {
    throw new Error(`Can't reach the SakayApp server at ${API_URL}.`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : `Server error (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  routes: () => request<RouteInfo[]>('/routes'),
  landmarks: () => request<Landmark[]>('/landmarks'),
  nearbyRoutes: (p: LatLng) => request<NearbyRoute[]>(`/routes/nearby?lat=${p.lat}&lng=${p.lng}`),
  plan: (origin: LatLng, destination: LatLng, riderType: RiderType) =>
    request<PlanResponse>('/trips/plan', {
      method: 'POST',
      body: JSON.stringify({ origin, destination, rider_type: riderType }),
    }),
};
