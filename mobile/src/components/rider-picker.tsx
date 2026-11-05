// Regular / Student / Senior / PWD, for the fare.
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Space, useColors } from '@/constants/theme';
import { RIDER_LABELS } from '@/lib/format';
import type { RiderType } from '@/lib/types';

export function RiderPicker({ value, onChange }: { value: RiderType; onChange: (r: RiderType) => void }) {
  const c = useColors();
  return (
    <View style={[styles.group, { backgroundColor: c.surface }]} accessibilityRole="radiogroup">
      {(Object.keys(RIDER_LABELS) as RiderType[]).map((r) => {
        const on = r === value;
        return (
          <Pressable
            key={r}
            onPress={() => onChange(r)}
            accessibilityRole="radio"
            accessibilityState={{ selected: on }}
            style={[styles.option, on && { backgroundColor: c.accent }]}>
            <Text style={[styles.label, { color: on ? c.accentText : c.text }]}>{RIDER_LABELS[r]}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  group: { flexDirection: 'row', borderRadius: 10, padding: 3, marginVertical: Space.sm },
  option: { flex: 1, paddingVertical: 7, borderRadius: 8, alignItems: 'center' },
  label: { fontSize: 13, fontWeight: '600' },
});
