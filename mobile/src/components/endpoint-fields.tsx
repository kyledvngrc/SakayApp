// The From / To rows at the top of the results panel.
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { Space, useColors } from '@/constants/theme';
import type { Endpoint } from '@/lib/types';

type Props = {
  origin: Endpoint | null;
  destination: Endpoint | null;
  onEdit: (which: 'origin' | 'destination') => void;
  onSwap: () => void;
};

export function EndpointFields({ origin, destination, onEdit, onSwap }: Props) {
  const c = useColors();
  const row = (which: 'origin' | 'destination', e: Endpoint | null) => (
    <Pressable
      onPress={() => onEdit(which)}
      accessibilityRole="button"
      accessibilityLabel={`${which === 'origin' ? 'Start' : 'Destination'}: ${e?.label ?? 'not set'}`}
      style={[styles.field, { backgroundColor: c.surface }]}>
      <Icon
        name={which === 'origin' ? 'circle.fill' : 'mappin'}
        color={which === 'origin' ? c.start : c.end}
        size={12}
        fallback={which === 'origin' ? '●' : '◆'}
      />
      <Text style={[styles.value, { color: e ? c.text : c.textSecondary }]} numberOfLines={1}>
        {e?.label ?? (which === 'origin' ? 'Choose start' : 'Where to?')}
      </Text>
    </Pressable>
  );
  return (
    <View style={styles.wrap}>
      <View style={styles.fields}>
        {row('origin', origin)}
        {row('destination', destination)}
      </View>
      <Pressable onPress={onSwap} accessibilityLabel="Swap start and destination" hitSlop={8} style={styles.swap}>
        <Icon name="arrow.up.arrow.down" color={c.textSecondary} size={18} fallback="⇅" />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center', gap: Space.sm },
  fields: { flex: 1, gap: 6 },
  field: { flexDirection: 'row', alignItems: 'center', gap: Space.sm, borderRadius: 10, paddingHorizontal: Space.md, paddingVertical: 10 },
  value: { fontSize: 15, flex: 1 },
  swap: { padding: Space.xs },
});
