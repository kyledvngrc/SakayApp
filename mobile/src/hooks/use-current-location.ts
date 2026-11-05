// The commuter's position from the phone's GPS (foreground only).
import * as Location from 'expo-location';
import { useCallback, useEffect, useState } from 'react';

import type { LatLng } from '@/lib/types';

export type LocationState =
  | { status: 'loading' }
  | { status: 'denied' }
  | { status: 'unavailable' }
  | { status: 'ok'; point: LatLng };

/** Asks for permission, then reports a quick last-known fix and a fresh one. */
async function readLocation(report: (s: LocationState) => void): Promise<void> {
  const { granted } = await Location.requestForegroundPermissionsAsync();
  if (!granted) return report({ status: 'denied' });
  const last = await Location.getLastKnownPositionAsync().catch(() => null);
  if (last) report({ status: 'ok', point: { lat: last.coords.latitude, lng: last.coords.longitude } });
  try {
    const now = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
    report({ status: 'ok', point: { lat: now.coords.latitude, lng: now.coords.longitude } });
  } catch {
    if (!last) report({ status: 'unavailable' });
  }
}

export function useCurrentLocation() {
  const [state, setState] = useState<LocationState>({ status: 'loading' });

  useEffect(() => {
    let alive = true;
    readLocation((s) => alive && setState(s));
    return () => {
      alive = false;
    };
  }, []);

  const refresh = useCallback(() => readLocation(setState), []);

  return { location: state, refresh };
}
