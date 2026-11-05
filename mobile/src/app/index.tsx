// Home: the map with a bottom sheet that moves through
// home -> search -> (pick on map) -> results -> trip.
import { useQuery } from '@tanstack/react-query';
import * as Haptics from 'expo-haptics';
import { useEffect, useMemo, useRef, useState } from 'react';
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
import { useRiderType } from '@/hooks/use-rider-type';
import { api } from '@/lib/api';
import { distanceText, peso } from '@/lib/format';
import { nearestLandmark, toCoord } from '@/lib/geo';
import type { Endpoint, LatLng } from '@/lib/types';

type Mode = 'home' | 'search' | 'pick' | 'results' | 'trip';
type Which = 'origin' | 'destination';

export default function HomeScreen() {
  const c = useColors();
  const insets = useSafeAreaInsets();
  const heights = useSheetHeights();
  const mapRef = useRef<MapView>(null);

  const { location, refresh: refreshLocation } = useCurrentLocation();
  const [rider, setRider] = useRiderType();

  const [mode, setMode] = useState<Mode>('home');
  const [sheet, setSheet] = useState<SheetSize>('half');
  const [editing, setEditing] = useState<Which>('destination');
  const [query, setQuery] = useState('');
  const [origin, setOrigin] = useState<Endpoint | null>(null);
  const [destination, setDestination] = useState<Endpoint | null>(null);
  const [selected, setSelected] = useState(0);
  const mapCenter = useRef<LatLng | null>(null);

  const myLocation: Endpoint | null =
    location.status === 'ok' ? { label: 'My location', point: location.point, isMyLocation: true } : null;
  const start = origin ?? myLocation;

  const routes = useQuery({ queryKey: ['routes'], queryFn: api.routes });
  const landmarks = useQuery({ queryKey: ['landmarks'], queryFn: api.landmarks });
  const nearby = useQuery({
    queryKey: ['nearby', myLocation && Math.round(myLocation.point.lat * 2000), myLocation && Math.round(myLocation.point.lng * 2000)],
    queryFn: () => api.nearbyRoutes(myLocation!.point),
    enabled: !!myLocation && mode === 'home',
  });
  const plan = useQuery({
    queryKey: ['plan', start?.point, destination?.point, rider],
    queryFn: () => api.plan(start!.point, destination!.point, rider),
    enabled: !!start && !!destination && (mode === 'results' || mode === 'trip'),
  });

  const trips = plan.data?.trips ?? [];
  const trip = mode === 'results' || mode === 'trip' ? trips[selected] ?? null : null;

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

  const describe = (p: LatLng): string => {
    const lm = nearestLandmark(p, landmarks.data ?? []);
    return lm ? `Near ${lm.name}` : 'Dropped pin';
  };

  const setEndpoint = (which: Which, e: Endpoint | null) => {
    if (which === 'origin') setOrigin(e?.isMyLocation ? null : e);
    else setDestination(e);
    const nextStart = which === 'origin' ? e ?? myLocation : start;
    const nextDest = which === 'destination' ? e : destination;
    setSelected(0);
    if (nextStart && nextDest) {
      setMode('results');
      setSheet('half');
    } else {
      setEditing(nextStart ? 'destination' : 'origin');
      setMode('search');
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
    const p = mapCenter.current;
    if (!p) return;
    Haptics.selectionAsync().catch(() => {});
    setEndpoint(editing, { label: describe(p), point: p });
  };

  const goHome = () => {
    setMode('home');
    setSheet('half');
    setDestination(null);
    setOrigin(null);
  };

  const swap = () => {
    if (!destination) return;
    const oldStart = start;
    setOrigin(destination);
    setDestination(oldStart);
    setSelected(0);
  };

  const onLongPress = (p: LatLng) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    const which: Which = mode === 'search' || mode === 'pick' ? editing : 'destination';
    setEndpoint(which, { label: describe(p), point: p });
  };

  const recenter = () => {
    if (location.status === 'ok') {
      mapRef.current?.animateToRegion({ ...toCoord(location.point), latitudeDelta: 0.02, longitudeDelta: 0.02 });
    } else {
      refreshLocation();
    }
  };

  const filteredLandmarks = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (landmarks.data ?? [])
      .filter((l) => !q || l.name.toLowerCase().includes(q) || (l.description ?? '').toLowerCase().includes(q))
      .slice(0, 30);
  }, [landmarks.data, query]);

  const styles = makeStyles(c);

  // ------------------------------------------------------------------ panels
  const header = (() => {
    if (mode === 'home') {
      return (
        <View style={styles.headerPad}>
          <Pressable onPress={() => openSearch('destination')} style={styles.whereTo} accessibilityRole="search">
            <Icon name="magnifyingglass" color={c.textSecondary} fallback="⌕" />
            <Text style={styles.whereToText}>Where to?</Text>
          </Pressable>
        </View>
      );
    }
    if (mode === 'search') {
      return (
        <View style={styles.headerPad}>
          <View style={styles.searchRow}>
            <Pressable onPress={() => (destination || origin ? setMode('results') : goHome())} hitSlop={10} accessibilityLabel="Back">
              <Icon name="chevron.left" color={c.text} size={20} fallback="‹" />
            </Pressable>
            <TextInput
              autoFocus
              value={query}
              onChangeText={setQuery}
              placeholder={editing === 'origin' ? 'Search a start point' : 'Search a destination'}
              placeholderTextColor={c.textSecondary}
              style={styles.input}
              returnKeyType="search"
              clearButtonMode="while-editing"
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
            <Pressable onPress={() => setMode('search')} style={[styles.button, styles.secondary]}>
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
            <Pressable onPress={goHome} hitSlop={10} accessibilityLabel="Close trip planner">
              <Icon name="xmark" color={c.text} size={18} fallback="✕" />
            </Pressable>
            <View style={{ flex: 1 }}>
              <EndpointFields origin={start} destination={destination} onEdit={openSearch} onSwap={swap} />
            </View>
          </View>
          <RiderPicker value={rider} onChange={setRider} />
        </View>
      );
    }
    // trip
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

  const body = (() => {
    if (mode === 'home') {
      return (
        <View>
          {location.status === 'denied' && (
            <Text style={styles.notice}>Location is off. Allow location for SakayApp in Settings, or choose a start point when planning.</Text>
          )}
          <Text style={styles.section}>Routes near you</Text>
          {location.status === 'loading' && <ActivityIndicator style={{ marginTop: Space.md }} />}
          {nearby.data?.length === 0 && <Text style={styles.muted}>No jeepney route passes within 500 m of you.</Text>}
          {nearby.error && <Text style={styles.notice}>{(nearby.error as Error).message}</Text>}
          {nearby.data?.map((r) => (
            <View key={r.code} style={styles.listRow}>
              <RouteBadge code={r.code} color={r.color} />
              <View style={{ flex: 1 }}>
                <Text style={styles.rowTitle} numberOfLines={1}>{r.name}</Text>
                <Text style={styles.muted}>
                  {distanceText(r.walk_m)} away · {r.kind === 'both' ? 'both ways' : r.kind === 'loop' ? 'loop' : 'one way'}
                </Text>
              </View>
            </View>
          ))}
          <Text style={styles.hint}>Tip: press and hold anywhere on the map to go there.</Text>
        </View>
      );
    }
    if (mode === 'search') {
      return (
        <View>
          {editing === 'origin' && myLocation && (
            <Option styles={styles} icon="location.fill" color={c.accent} label="My location" onPress={() => setEndpoint('origin', myLocation)} />
          )}
          <Option styles={styles} icon="map" color={c.accent} label="Choose on the map" onPress={startPicking} />
          {filteredLandmarks.length > 0 && <Text style={styles.section}>Places</Text>}
          {filteredLandmarks.map((l) => (
            <Option
              key={l.id}
              styles={styles}
              icon="mappin"
              color={c.textSecondary}
              label={l.name}
              sub={l.description ?? undefined}
              onPress={() => setEndpoint(editing, { label: l.name, point: { lat: l.lat, lng: l.lng } })}
            />
          ))}
          {query.trim() !== '' && filteredLandmarks.length === 0 && (
            <Text style={styles.muted}>No saved place matches “{query.trim()}”. Choose it on the map instead.</Text>
          )}
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
              onPress={() => {
                if (i === selected) {
                  setMode('trip');
                } else setSelected(i);
              }}
            />
          ))}
          {trips.length > 0 && (
            <Text style={styles.hint}>
              Tap a trip to show it on the map, tap again for directions. {plan.data?.estimates_note}
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
        routes={routes.data ?? []}
        trip={trip}
        origin={mode === 'results' || mode === 'trip' ? start : null}
        destination={mode === 'home' ? null : destination}
        bottomInset={heights[sheet]}
        onLongPress={onLongPress}
        onRegionChangeComplete={(p) => {
          mapCenter.current = p;
        }}
      />

      {mode === 'pick' && (
        <View pointerEvents="none" style={[styles.crosshair, { bottom: heights[sheet] / 2 }]}>
          <Icon name="mappin" color={editing === 'origin' ? c.start : c.end} size={36} fallback="📍" />
        </View>
      )}

      <Pressable
        onPress={recenter}
        accessibilityLabel="Show my location"
        style={[styles.fab, { bottom: Math.min(heights[sheet], heights.half) + Space.md }]}>
        <Icon name="location.fill" color={c.accent} fallback="◎" />
      </Pressable>

      {routes.error && (
        <View style={[styles.banner, { top: insets.top + Space.sm }]}>
          <Text style={styles.bannerText}>{(routes.error as Error).message}</Text>
        </View>
      )}

      <Sheet size={sheet} onSizeChange={setSheet} header={header}>
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
        <Text style={styles.rowTitle}>{label}</Text>
        {sub ? <Text style={styles.muted}>{sub}</Text> : null}
      </View>
    </Pressable>
  );
}

const makeStyles = (c: Colors) =>
  StyleSheet.create({
    screen: { flex: 1, backgroundColor: c.background },
    headerPad: { paddingHorizontal: Space.lg, paddingBottom: Space.sm },
    whereTo: { flexDirection: 'row', alignItems: 'center', gap: Space.sm, backgroundColor: c.surface, borderRadius: 12, padding: Space.md },
    whereToText: { fontSize: 17, color: c.textSecondary },
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
    notice: { backgroundColor: c.warnBg, color: c.warnText, borderRadius: 8, padding: Space.md, marginVertical: Space.sm, overflow: 'hidden' },
    crosshair: { position: 'absolute', top: 0, left: 0, right: 0, alignItems: 'center', justifyContent: 'center' },
    fab: {
      position: 'absolute', right: Space.lg, width: 44, height: 44, borderRadius: 22, backgroundColor: c.background,
      alignItems: 'center', justifyContent: 'center', shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 6, shadowOffset: { width: 0, height: 2 },
    },
    banner: { position: 'absolute', left: Space.lg, right: Space.lg, backgroundColor: c.warnBg, borderRadius: 10, padding: Space.md },
    bannerText: { color: c.warnText },
  });
