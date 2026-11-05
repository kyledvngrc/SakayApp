// Routes tab: routes near you on top, then every route.
import { useQuery } from '@tanstack/react-query';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { KIND_TEXT, RouteRow } from '@/components/route-row';
import { Space, useColors } from '@/constants/theme';
import { useCurrentLocation } from '@/hooks/use-current-location';
import { api } from '@/lib/api';
import { distanceText } from '@/lib/format';

export default function RoutesScreen() {
  const c = useColors();
  const insets = useSafeAreaInsets();
  const { location, refresh } = useCurrentLocation();
  const here = location.status === 'ok' ? location.point : null;

  const routes = useQuery({ queryKey: ['routes'], queryFn: api.routes });
  const nearby = useQuery({
    queryKey: ['nearby', here && Math.round(here.lat * 2000), here && Math.round(here.lng * 2000)],
    queryFn: () => api.nearbyRoutes(here!),
    enabled: !!here,
  });

  const all = [...(routes.data ?? [])].sort((a, b) => a.code.localeCompare(b.code));
  const reload = () => {
    refresh();
    routes.refetch();
    nearby.refetch();
  };

  return (
    <ScrollView
      style={{ backgroundColor: c.background }}
      contentContainerStyle={[styles.page, { paddingTop: insets.top + Space.md }]}
      refreshControl={<RefreshControl refreshing={routes.isRefetching} onRefresh={reload} />}>
      <Text style={[styles.title, { color: c.text }]}>Routes</Text>

      <Text style={[styles.section, { color: c.textSecondary }]}>Near you</Text>
      {location.status === 'loading' || nearby.isLoading ? (
        <ActivityIndicator style={styles.spinner} />
      ) : location.status !== 'ok' ? (
        <Text style={[styles.muted, { color: c.textSecondary }]}>
          {location.status === 'denied'
            ? 'Allow location for SakayApp in Settings to see routes near you.'
            : 'Your location is not available right now.'}
        </Text>
      ) : nearby.data?.length ? (
        nearby.data.map((r) => (
          <RouteRow key={r.code} code={r.code} name={r.name} color={r.color}
            detail={`${distanceText(r.walk_m)} away · ${KIND_TEXT[r.kind]}`} />
        ))
      ) : (
        <Text style={[styles.muted, { color: c.textSecondary }]}>No jeepney route passes within 500 m of you.</Text>
      )}

      <Text style={[styles.section, { color: c.textSecondary }]}>All routes</Text>
      {routes.isLoading && <ActivityIndicator style={styles.spinner} />}
      {routes.error && <Text style={[styles.notice, { backgroundColor: c.warnBg, color: c.warnText }]}>{(routes.error as Error).message}</Text>}
      {all.map((r) => (
        <RouteRow key={r.code} code={r.code} name={r.name} color={r.color}
          detail={`${KIND_TEXT[r.kind]} · ${r.length_km.toFixed(1)} km`} />
      ))}
      <View style={{ height: Space.xl }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { paddingHorizontal: Space.lg },
  title: { fontSize: 32, fontWeight: '700', marginBottom: Space.sm },
  section: { fontSize: 13, fontWeight: '600', textTransform: 'uppercase', marginTop: Space.xl, marginBottom: Space.xs },
  muted: { fontSize: 14, paddingVertical: Space.sm },
  spinner: { marginVertical: Space.md },
  notice: { borderRadius: 8, padding: Space.md, overflow: 'hidden' },
});
