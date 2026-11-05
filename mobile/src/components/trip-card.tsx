// One trip option in the results list: route badges, fare, ride and walk distance.
// Tapping the card shows the trip on the map; Start opens its directions.
import { Fragment } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { RouteBadge } from '@/components/route-badge';
import { Space, useColors } from '@/constants/theme';
import { distanceText, peso } from '@/lib/format';
import type { Trip } from '@/lib/types';

type Props = { trip: Trip; selected?: boolean; onPress: () => void; onStart: () => void };

export function TripCard({ trip, selected, onPress, onStart }: Props) {
  const c = useColors();
  const rides = trip.segments.filter((s) => s.kind === 'ride');
  const transfers = trip.transfers === 0 ? 'No transfer' : trip.transfers === 1 ? '1 transfer' : `${trip.transfers} transfers`;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`Ride ${trip.route_codes.join(' then ')}, ${transfers}`}
      style={({ pressed }) => [
        styles.card,
        { backgroundColor: c.surface, borderColor: selected ? c.accent : 'transparent', opacity: pressed ? 0.7 : 1 },
      ]}>
      <View style={styles.row}>
        <View style={styles.badges}>
          <Icon name="figure.walk" color={c.walk} fallback="🚶" />
          {rides.map((r, i) => (
            <Fragment key={i}>
              <Icon name="chevron.right" color={c.textSecondary} size={11} fallback="›" />
              <RouteBadge code={r.route.code} color={r.route.color} />
            </Fragment>
          ))}
        </View>
        <Text style={[styles.fare, { color: c.text }]}>
          {trip.fare_available && trip.total_fare != null ? peso(trip.total_fare) : 'Fare n/a'}
        </Text>
      </View>
      <View style={styles.footer}>
        <Text style={[styles.meta, { color: c.textSecondary }]}>
          {transfers} · {trip.ride_km.toFixed(1)} km ride · {distanceText(trip.walking_m)} walk
        </Text>
        <Pressable
          onPress={onStart}
          accessibilityRole="button"
          accessibilityLabel="Start this trip"
          hitSlop={6}
          style={({ pressed }) => [styles.start, { backgroundColor: c.accent, opacity: pressed ? 0.7 : 1 }]}>
          <Text style={[styles.startText, { color: c.accentText }]}>Start</Text>
        </Pressable>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: 12, padding: Space.md, marginBottom: Space.sm, borderWidth: 2 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: Space.sm },
  badges: { flexDirection: 'row', alignItems: 'center', gap: 6, flexShrink: 1, flexWrap: 'wrap' },
  fare: { fontSize: 17, fontWeight: '700' },
  footer: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: Space.sm, marginTop: Space.sm },
  meta: { fontSize: 13, flexShrink: 1 },
  start: { paddingHorizontal: Space.lg, paddingVertical: 7, borderRadius: 18 },
  startText: { fontSize: 15, fontWeight: '700' },
});
