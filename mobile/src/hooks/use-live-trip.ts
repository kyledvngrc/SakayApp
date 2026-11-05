// Follows the commuter along a trip with foreground GPS and raises alerts.
import * as Haptics from 'expo-haptics';
import * as Location from 'expo-location';
import * as Speech from 'expo-speech';
import { useEffect, useReducer, useState } from 'react';
import { Vibration } from 'react-native';

import { nextStep, previousStep, spoken, startTrip, update, type LiveEvent, type LiveState } from '@/lib/live';
import type { Trip } from '@/lib/types';

type Store = { live: LiveState; events: LiveEvent[]; seq: number };
type Action =
  | { type: 'fix'; lat: number; lng: number; accuracy: number | null }
  | { type: 'next' }
  | { type: 'back' };

function reduce(trip: Trip, store: Store, action: Action): Store {
  if (action.type === 'next') return { live: nextStep(trip, store.live), events: [], seq: store.seq };
  if (action.type === 'back') return { live: previousStep(trip, store.live), events: [], seq: store.seq };
  const { state, events } = update(trip, store.live, action);
  return { live: state, events, seq: events.length ? store.seq + 1 : store.seq };
}

export type GpsStatus = 'starting' | 'tracking' | 'denied' | 'error';

export function useLiveTrip(trip: Trip, soundOn: boolean) {
  const [store, dispatch] = useReducer((s: Store, a: Action) => reduce(trip, s, a), trip, (t) => ({
    live: startTrip(t),
    events: [],
    seq: 0,
  }));
  const [gps, setGps] = useState<GpsStatus>('starting');

  // GPS while the app is open (Expo Go has no background location).
  useEffect(() => {
    let sub: Location.LocationSubscription | null = null;
    let alive = true;
    (async () => {
      const { granted } = await Location.requestForegroundPermissionsAsync();
      if (!alive) return;
      if (!granted) return setGps('denied');
      try {
        sub = await Location.watchPositionAsync(
          { accuracy: Location.Accuracy.BestForNavigation, distanceInterval: 5, timeInterval: 1000 },
          (loc) => {
            setGps('tracking');
            dispatch({ type: 'fix', lat: loc.coords.latitude, lng: loc.coords.longitude, accuracy: loc.coords.accuracy });
          },
        );
        if (!alive) sub.remove();
      } catch {
        if (alive) setGps('error');
      }
    })();
    return () => {
      alive = false;
      sub?.remove();
    };
  }, []);

  // Alerts: vibration and haptics always, speech when sound is on.
  useEffect(() => {
    if (store.seq === 0) return;
    for (const e of store.events) {
      if (e.type === 'get-off-soon' || e.type === 'get-off-here') {
        Vibration.vibrate([0, 400, 200, 400]);
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning).catch(() => {});
      } else if (e.type === 'arrived') {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      } else if (e.type === 'off-route') {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => {});
      } else {
        Haptics.selectionAsync().catch(() => {});
      }
      const words = spoken(trip, e);
      if (soundOn && words) Speech.speak(words, { language: 'en-US' });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store.seq]);

  useEffect(() => () => {
    Speech.stop();
  }, []);

  return {
    live: store.live,
    gps,
    next: () => dispatch({ type: 'next' }),
    back: () => dispatch({ type: 'back' }),
  };
}
