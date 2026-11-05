// Step-by-step directions for one trip.
import { StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { RouteBadge } from '@/components/route-badge';
import { Space, useColors } from '@/constants/theme';
import { peso } from '@/lib/format';
import type { Trip } from '@/lib/types';

export function TripSteps({ trip }: { trip: Trip }) {
  const c = useColors();
  const last = trip.segments.length - 1;
  return (
    <View>
      {trip.segments.map((s, i) => {
        const color = s.kind === 'ride' ? s.route.color : c.walk;
        return (
          <View key={i} style={styles.step}>
            <View style={styles.rail}>
              {s.kind === 'ride' ? (
                <RouteBadge code={s.route.code} color={s.route.color} />
              ) : (
                <Icon name="figure.walk" color={c.walk} size={20} fallback="🚶" />
              )}
              {i < last && (
                <View
                  style={[
                    styles.line,
                    s.kind === 'ride' ? { backgroundColor: color } : { borderColor: color, borderStyle: 'dashed', borderLeftWidth: 2 },
                  ]}
                />
              )}
            </View>
            <View style={styles.text}>
              <Text style={[styles.instruction, { color: c.text }]}>{s.instruction}</Text>
              {s.kind === 'ride' && (
                <Text style={[styles.sub, { color: c.textSecondary }]}>
                  {s.fare != null ? `Fare ${peso(s.fare)} · ` : ''}Say “para” to the driver when you’re about to get off
                </Text>
              )}
            </View>
          </View>
        );
      })}
      <View style={styles.step}>
        <View style={styles.rail}>
          <Icon name="mappin.circle.fill" color={c.end} size={22} fallback="◉" />
        </View>
        <Text style={[styles.instruction, styles.text, { color: c.text }]}>Arrive at your destination</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  step: { flexDirection: 'row', gap: Space.md, minHeight: 56 },
  rail: { width: 48, alignItems: 'center' },
  line: { width: 4, flex: 1, marginVertical: 4, borderRadius: 2 },
  text: { flex: 1, paddingBottom: Space.md },
  instruction: { fontSize: 15, lineHeight: 21 },
  sub: { fontSize: 13, marginTop: 3 },
});
