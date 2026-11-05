// Plan tab: the map with a bottom sheet.
//   home    From / To fields
//   search  find a place for one field (addresses, places, landmarks)
//   pick    move the map under the pin to choose a point
//   results trip options          trip  step-by-step directions
import { useQuery } from '@tanstack/react-query';
import * as Haptics from 'expo-haptics';
import { useBottomTabBarHeight } from 'expo-router/js-tabs';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import type MapView from 'react-native-maps';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { EndpointFields } from '@/components/endpoint-fields';
import { Icon } from '@/components/icon';
import { RiderPicker } from '@/components/rider-picker';
import { RouteBadge } from '@/components/route-badge';
import { Sheet, useSheetHeights, type SheetSize } from '@/components/sheet';
import { TripCard } from '@/components/trip-card';
import { TripMap } from '@/components/trip-map';
import { TripSteps } from '@/components/trip-steps';
import { Space, useColors, type Colors } from '@/constants/theme';
import { useCurrentLocation } from '@/hooks/use-current-location';
import { useDebouncedValue } from '@/hooks/use-debounced-value';
import { useRiderType } from '@/hooks/use-rider-type';
import { api } from '@/lib/api';
import { peso } from '@/lib/format';
import { toCoord } from '@/lib/geo';
import type { Endpoint, LatLng } from '@/lib/types';

type Mode = 'home' | 'search' | 'pick' | 'results' | 'trip';
type Which = 'origin' | 'destination';
const DROPPED = 'Dropped pin';

export default function PlanScreen() {
  const c = useColors();
  const insets = useSafeAreaInsets();
  const tabBar = useBottomTabBarHeight();
  const heights = useSheetHeights(tabBar);
  const mapRef = useRef<MapView>(null);

  const { location, refresh: refreshLocation } = useCurrentLocation();
  const [rider, setRider] = useRiderType();

  const [mode, setMode] = useState<Mode>('home');
  const [sheet, setSheet] = useState<SheetSize>('peek');
  const [editing, setEditing] = useState<Which>('destination');
  const [query, setQuery] = useState('');
  const [origin, setOrigin] = useState<Endpoint | null>(null); // null = My location
  const [destination, setDestination] = useState<Endpoint | null>(null);
  const [selected, setSelected] = useState(0);
  const center = useRef<LatLng | null>(null); // map centre, for pick mode

  const myLocation: Endpoint | null =
    location.status === 'ok' ? { label: 'My location', point: location.point, isMyLocation: true } : null;
  const start = origin ?? myLocation;

  const searchText = useDebouncedValue(query.trim(), 350);
  const places = useQuery({
    queryKey: ['places', searchText.toLowerCase()],
    queryFn: () => api.searchPlaces(searchText),
    enabled: mode === 'search' && searchText.length >= 2,
    staleTime: 10 * 60_000,
  });
  const plan = useQuery({
    queryKey: ['plan', start?.point, destination?.point, rider],
    queryFn: () => api.plan(start!.point, destination!.point, rider),
    enabled: !!start && !!destination && (mode === 'results' || mode === 'trip'),
  });

  const trips = plan.data?.trips ?? [];
  const trip = mode === 'results' || mode === 'trip' ? (trips[selected] ?? null) : null;

  // Frame the chosen trip above the sheet.
  useEffect(() => {
    if (!trip) return;
    const coords = trip.segments.flatMap((s) => s.path.map(toCoord));
    mapRef.current?.fitToCoordinates(coords, {
      edgePadding: { top: insets.top + 40, right: 40, bottom: heights[sheet] + 30, left: 40 },
      animated: true,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trip, mode]);

  /** Replace "Dropped pin" with a nearby place name once the server knows it. */
  const relabel = (which: Which, p: LatLng) => {
    api.reverse(p).then(({ label }) => {
      const update = (e: Endpoint | null) => (e && e.point === p ? { ...e, label } : e);
      if (which === 'origin') setOrigin(update);
      else setDestination(update);
    }).catch(() => {});
  };

  const setEndpoint = (which: Which, e: Endpoint | null) => {
    if (which === 'origin') setOrigin(e?.isMyLocation ? null : e);
    else setDestination(e);
    if (e && e.label === DROPPED) relabel(which, e.point);
    const nextStart = which === 'origin' ? (e ?? myLocation) : start;
    const nextDest = which === 'destination' ? e : destination;
    setSelected(0);
    setQuery('');
    if (nextStart && nextDest) {
      setMode('results');
      setSheet('half');
    } else {
      setMode('home');
      setSheet('peek');
    }
  };

  const openSearch = (which: Which) => {
    setEditing(which);
    setQuery('');
    setMode('search');
    setSheet('full');
  };

  const startPicking = () => {
    setMode('pick');
    setSheet('peek');
  };

  const confirmPick = () => {
    const p = center.current;
    if (!p) return;
    Haptics.selectionAsync().catch(() => {});
    setEndpoint(editing, { label: DROPPED, point: p });
  };

  const backFromSearch = () => {
    setMode(start && destination ? 'results' : 'home');
    setSheet(start && destination ? 'half' : 'peek');
  };

  const reset = () => {
    setMode('home');
    setSheet('peek');
    setDestination(null);
    setOrigin(null);
  };

  const swap = () => {
    if (!destination) return;
    const oldStart = start;
    setOrigin(destination.isMyLocation ? null : destination);
    setDestination(oldStart);
    setSelected(0);
  };

  const onLongPress = (p: LatLng) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    const which: Which = mode === 'search' || mode === 'pick' ? editing : 'destination';
    setEndpoint(which, { label: DROPPED, point: p });
  };

  const recenter = () => {
    if (location.status === 'ok') {
      mapRef.current?.animateToRegion({ ...toCoord(location.point), latitudeDelta: 0.02, longitudeDelta: 0.02 });
    } else {
      refreshLocation();
    }
  };

  const styles = makeStyles(c);
  const fields = <EndpointFields origin={start} destination={destination} onEdit={openSearch} onSwap={swap} />;

  // ------------------------------------------------------------------ header
  const header = (() => {
    if (mode === 'home') {
      return <View style={styles.headerPad}>{fields}</View>;
    }
    if (mode === 'search') {
      return (
        <View style={styles.headerPad}>
          <View style={styles.searchRow}>
            <Pressable onPress={backFromSearch} hitSlop={10} accessibilityLabel="Back">
              <Icon name="chevron.left" color={c.text} size={20} fallback="‹" />
            </Pressable>
            <TextInput
              autoFocus
              value={query}
              onChangeText={setQuery}
              placeholder={editing === 'origin' ? 'Search a start: place, street or address' : 'Search a place, street or address'}
              placeholderTextColor={c.textSecondary}
              style={styles.input}
              returnKeyType="search"
              clearButtonMode="while-editing"
              autoCorrect={false}
            />
          </View>
        </View>
      );
    }
    if (mode === 'pick') {
      return (
        <View style={styles.headerPad}>
          <Text style={styles.title}>Move the map to your {editing === 'origin' ? 'start point' : 'destination'}</Text>
          <View style={styles.buttonRow}>
            <Pressable onPress={() => { setMode('search'); setSheet('full'); }} style={[styles.button, styles.secondary]}>
              <Text style={styles.secondaryText}>Cancel</Text>
            </Pressable>
            <Pressable onPress={confirmPick} style={[styles.button, styles.primary]}>
              <Text style={styles.primaryText}>Set {editing === 'origin' ? 'start' : 'destination'}</Text>
            </Pressable>
          </View>
        </View>
      );
    }
    if (mode === 'results') {
      return (
        <View style={styles.headerPad}>
          <View style={styles.searchRow}>
            <Pressable onPress={reset} hitSlop={10} accessibilityLabel="Clear trip">
              <Icon name="xmark" color={c.text} size={18} fallback="✕" />
            </Pressable>
            <View style={{ flex: 1 }}>{fields}</View>
          </View>
          <RiderPicker value={rider} onChange={setRider} />
        </View>
      );
    }
    return (
      <View style={styles.headerPad}>
        <View style={styles.searchRow}>
          <Pressable onPress={() => setMode('results')} hitSlop={10} accessibilityLabel="Back to trip options">
            <Icon name="chevron.left" color={c.text} size={20} fallback="‹" />
          </Pressable>
          <View style={styles.badgeRow}>
            {trip?.segments.map((s, i) => (s.kind === 'ride' ? <RouteBadge key={i} code={s.route.code} color={s.route.color} large /> : null))}
          </View>
          <Text style={styles.fareBig}>
            {trip?.fare_available && trip.total_fare != null ? peso(trip.total_fare) : 'Fare n/a'}
          </Text>
        </View>
      </View>
    );
  })();

  // ------------------------------------------------------------------ body
  const body = (() => {
    if (mode === 'home') {
      return (
        <View>
          {location.status === 'denied' && (
            <Text style={styles.notice}>Location is off, so set a start point. To use your location, allow it for SakayApp in Settings.</Text>
          )}
          <Text style={[styles.hint, styles.homeHint]}>Tap a field to search a place, street or address. You can also press and hold on the map.</Text>
        </View>
      );
    }
    if (mode === 'search') {
      const results = places.data?.results ?? [];
      const searching = searchText.length >= 2;
      return (
        <View>
          {editing === 'origin' && myLocation && (
            <Option styles={styles} icon="location.fill" color={c.accent} label="My location" onPress={() => setEndpoint('origin', myLocation)} />
          )}
          <Option styles={styles} icon="map" color={c.accent} label="Choose on the map" onPress={startPicking} />
          {searching && places.isFetching && results.length === 0 && <ActivityIndicator style={{ marginTop: Space.md }} />}
          {results.length > 0 && <Text style={styles.section}>Results</Text>}
          {results.map((r, i) => (
            <Option
              key={`${r.name}-${i}`}
              styles={styles}
              icon={r.source === 'landmark' ? 'star.fill' : 'mappin'}
              color={r.source === 'landmark' ? '#F2A900' : c.textSecondary}
              label={r.name}
              sub={r.detail || undefined}
              onPress={() => setEndpoint(editing, { label: r.name, point: { lat: r.lat, lng: r.lng } })}
            />
          ))}
          {searching && places.data && results.length === 0 && (
            <Text style={styles.muted}>
              {places.data.search_available
                ? `Nothing found for “${searchText}” in Davao City. Try another spelling, or choose it on the map.`
                : 'Address search is unavailable right now. Choose the place on the map instead.'}
            </Text>
          )}
          {places.error && <Text style={styles.notice}>{(places.error as Error).message}</Text>}
          {results.length > 0 && <Text style={styles.hint}>{places.data?.attribution}</Text>}
        </View>
      );
    }
    if (mode === 'results') {
      if (plan.isLoading) return <ActivityIndicator style={{ marginTop: Space.lg }} />;
      if (plan.error) return <Text style={styles.notice}>{(plan.error as Error).message}</Text>;
      return (
        <View>
          {plan.data?.notice && <Text style={styles.notice}>{plan.data.notice}</Text>}
          {trips.map((t, i) => (
            <TripCard
              key={i}
              trip={t}
              selected={i === selected}
              onPress={() => setSelected(i)}
              onStart={() => {
                setSelected(i);
                setMode('trip');
              }}
            />
          ))}
          {trips.length > 0 && (
            <Text style={styles.hint}>
              Tap a trip to see it on the map, or Start for directions. {plan.data?.estimates_note}
              {plan.data?.fare_source ? ` Fares: ${plan.data.fare_source}.` : ''}
            </Text>
          )}
        </View>
      );
    }
    if (mode === 'trip' && trip) return <TripSteps trip={trip} />;
    return null;
  })();

  return (
    <View style={styles.screen}>
      <TripMap
        ref={mapRef}
        trip={trip}
        origin={mode === 'pick' ? null : start}
        destination={mode === 'pick' ? null : destination}
        bottomInset={heights[sheet]}
        onLongPress={onLongPress}
        onRegionChangeComplete={(p) => {
          center.current = p;
        }}
      />

      {mode === 'pick' && (
        <View pointerEvents="none" style={[styles.crosshair, { bottom: heights[sheet] }]}>
          <Icon name="mappin" color={editing === 'origin' ? c.start : c.end} size={36} fallback="📍" />
        </View>
      )}

      {mode !== 'search' && (
        <Pressable
          onPress={recenter}
          accessibilityLabel="Show my location"
          style={[styles.fab, { bottom: Math.min(heights[sheet], heights.half) + Space.md }]}>
          <Icon name="location.fill" color={c.accent} fallback="◎" />
        </Pressable>
      )}

      <Sheet size={sheet} reservedBelow={tabBar} onSizeChange={setSheet} header={header}>
        {body}
      </Sheet>
    </View>
  );
}

type OptionProps = {
  styles: ReturnType<typeof makeStyles>;
  icon: Parameters<typeof Icon>[0]['name'];
  color: string;
  label: string;
  sub?: string;
  onPress: () => void;
};

function Option({ styles, icon, color, label, sub, onPress }: OptionProps) {
  return (
    <Pressable onPress={onPress} style={styles.listRow} accessibilityRole="button">
      <View style={styles.optionIcon}>
        <Icon name={icon} color={color} fallback="•" />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowTitle} numberOfLines={1}>{label}</Text>
        {sub ? <Text style={styles.muted} numberOfLines={1}>{sub}</Text> : null}
      </View>
    </Pressable>
  );
}

const makeStyles = (c: Colors) =>
  StyleSheet.create({
    screen: { flex: 1, backgroundColor: c.background },
    headerPad: { paddingHorizontal: Space.lg, paddingBottom: Space.sm },
    searchRow: { flexDirection: 'row', alignItems: 'center', gap: Space.md },
    input: { flex: 1, fontSize: 17, color: c.text, backgroundColor: c.surface, borderRadius: 10, paddingHorizontal: Space.md, paddingVertical: 10 },
    title: { fontSize: 16, fontWeight: '600', color: c.text, marginBottom: Space.sm },
    buttonRow: { flexDirection: 'row', gap: Space.sm },
    button: { flex: 1, borderRadius: 10, paddingVertical: 12, alignItems: 'center' },
    primary: { backgroundColor: c.accent },
    primaryText: { color: c.accentText, fontWeight: '700', fontSize: 15 },
    secondary: { backgroundColor: c.surface },
    secondaryText: { color: c.text, fontWeight: '600', fontSize: 15 },
    badgeRow: { flex: 1, flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
    fareBig: { fontSize: 20, fontWeight: '700', color: c.text },
    section: { fontSize: 13, fontWeight: '600', color: c.textSecondary, textTransform: 'uppercase', marginTop: Space.md, marginBottom: Space.xs },
    listRow: { flexDirection: 'row', alignItems: 'center', gap: Space.md, paddingVertical: 10 },
    optionIcon: { width: 32, height: 32, borderRadius: 16, backgroundColor: c.surface, alignItems: 'center', justifyContent: 'center' },
    rowTitle: { fontSize: 15, color: c.text },
    muted: { fontSize: 13, color: c.textSecondary, marginTop: 2 },
    hint: { fontSize: 12, color: c.textSecondary, marginTop: Space.md },
    homeHint: { marginTop: 2 }, // sits right under the From / To fields
    notice: { backgroundColor: c.warnBg, color: c.warnText, borderRadius: 8, padding: Space.md, marginVertical: Space.sm, overflow: 'hidden' },
    crosshair: { position: 'absolute', top: 0, left: 0, right: 0, alignItems: 'center', justifyContent: 'center', paddingBottom: 36 },
    fab: {
      position: 'absolute', right: Space.lg, width: 44, height: 44, borderRadius: 22, backgroundColor: c.background,
      alignItems: 'center', justifyContent: 'center', shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 6, shadowOffset: { width: 0, height: 2 },
    },
  });
