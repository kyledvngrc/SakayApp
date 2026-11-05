// One route on the map, from start (S) to end (E).
import { useQuery } from '@tanstack/react-query';
import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import MapView, { Marker, Polyline } from 'react-native-maps';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { RouteBadge } from '@/components/route-badge';
import { KIND_TEXT } from '@/components/route-row';
import { Space, useColors } from '@/constants/theme';
import { api } from '@/lib/api';
import { DAVAO } from '@/lib/geo';

const KIND_HINT = {
  both: 'Runs both ways on the same streets.',
  oneway: 'Runs one way only, in the direction shown from S to E.',
  loop: 'Runs one way around a loop, in the direction shown.',
} as const;

export default function RouteScreen() {
  const { code } = useLocalSearchParams<{ code: string }>();
  const c = useColors();
  const insets = useSafeAreaInsets();
  const mapRef = useRef<MapView>(null);
  const route = useQuery({ queryKey: ['route', code], queryFn: () => api.route(code) });

  const coords = (route.data?.path_geojson.coordinates ?? []).map(([lng, lat]) => ({ latitude: lat, longitude: lng }));

  useEffect(() => {
    if (coords.length < 2) return;
    const t = setTimeout(() => mapRef.current?.fitToCoordinates(coords, {
      edgePadding: { top: 60, right: 40, bottom: 200, left: 40 }, animated: false,
    }), 50);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route.data]);

  return (
    <View style={{ flex: 1, backgroundColor: c.background }}>
      <Stack.Screen options={{ title: route.data ? route.data.code : 'Route' }} />
      <MapView ref={mapRef} style={StyleSheet.absoluteFill} initialRegion={DAVAO} showsUserLocation>
        {coords.length > 1 && (
          <>
            <Polyline coordinates={coords} strokeColor={route.data!.color} strokeWidth={6} />
            <Marker coordinate={coords[0]} pinColor={c.start} title="Start (S)" />
            <Marker coordinate={coords[coords.length - 1]} pinColor={c.end} title="End (E)" />
          </>
        )}
      </MapView>
      <View style={[styles.card, { backgroundColor: c.background, borderColor: c.border, paddingBottom: insets.bottom + Space.lg }]}>
        {route.isLoading && <ActivityIndicator />}
        {route.error && <Text style={{ color: c.warnText }}>{(route.error as Error).message}</Text>}
        {route.data && (
          <>
            <View style={styles.titleRow}>
              <RouteBadge code={route.data.code} color={route.data.color} large />
              <Text style={[styles.name, { color: c.text }]} numberOfLines={2}>{route.data.name}</Text>
            </View>
            <Text style={[styles.meta, { color: c.textSecondary }]}>
              {KIND_TEXT[route.data.kind]} · {route.data.length_km.toFixed(1)} km · {route.data.vehicle_type}
            </Text>
            <Text style={[styles.meta, { color: c.textSecondary }]}>{KIND_HINT[route.data.kind]}</Text>
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { position: 'absolute', left: 0, right: 0, bottom: 0, padding: Space.lg, borderTopLeftRadius: 18, borderTopRightRadius: 18, borderWidth: StyleSheet.hairlineWidth },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: Space.md },
  name: { fontSize: 18, fontWeight: '600', flex: 1 },
  meta: { fontSize: 14, marginTop: Space.sm },
});
