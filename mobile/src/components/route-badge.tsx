// A route's code on its color, like the sign on the jeepney.
import { StyleSheet, Text, View } from 'react-native';

import { textOn } from '@/lib/format';

export function RouteBadge({ code, color, large }: { code: string; color: string; large?: boolean }) {
  return (
    <View style={[styles.badge, large && styles.large, { backgroundColor: color }]}>
      <Text style={[styles.text, large && styles.largeText, { color: textOn(color) }]} numberOfLines={1}>
        {code}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { paddingHorizontal: 7, paddingVertical: 3, borderRadius: 5, minWidth: 36, alignItems: 'center' },
  large: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 7 },
  text: { fontWeight: '700', fontSize: 13 },
  largeText: { fontSize: 16 },
});
