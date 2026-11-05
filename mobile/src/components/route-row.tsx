// One route in a list: badge, name, direction and length or distance away.
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { RouteBadge } from '@/components/route-badge';
import { Space, useColors } from '@/constants/theme';

export const KIND_TEXT = { both: 'Both ways', oneway: 'One way', loop: 'Loop' } as const;

type Props = { code: string; name: string; color: string; detail: string };

export function RouteRow({ code, name, color, detail }: Props) {
  const c = useColors();
  return (
    <Link href={{ pathname: '/route/[code]', params: { code } }} asChild>
      <Pressable style={({ pressed }) => [styles.row, { borderColor: c.border, opacity: pressed ? 0.6 : 1 }]}>
        <RouteBadge code={code} color={color} />
        <View style={styles.text}>
          <Text style={[styles.name, { color: c.text }]} numberOfLines={1}>{name}</Text>
          <Text style={[styles.detail, { color: c.textSecondary }]}>{detail}</Text>
        </View>
        <Icon name="chevron.right" color={c.textSecondary} size={13} fallback="›" />
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: Space.md, paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth },
  text: { flex: 1 },
  name: { fontSize: 16 },
  detail: { fontSize: 13, marginTop: 2 },
});
