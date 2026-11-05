// A draggable bottom sheet over the map: peek, half or full height.
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Animated, PanResponder, Pressable, ScrollView, StyleSheet, useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Space, useColors } from '@/constants/theme';

export type SheetSize = 'peek' | 'half' | 'full';

type Props = {
  size: SheetSize;
  /** Space below the screen that the screen doesn't own, e.g. a tab bar. The
   *  sheet sits at the bottom of its screen, so this only shrinks the heights. */
  reservedBelow?: number;
  onSizeChange: (size: SheetSize) => void;
  header?: ReactNode; // stays visible; dragging it moves the sheet
  children?: ReactNode; // scrolls
};

/** Sheet heights within the screen (window minus anything below it, like a tab bar). */
export function useSheetHeights(reservedBelow = 0) {
  const { height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  return useMemo(() => {
    const screen = height - reservedBelow;
    const bottomInset = reservedBelow ? 0 : insets.bottom;
    return {
      peek: 172 + bottomInset, // grabber, From / To fields and a two-line hint
      half: Math.round(screen * 0.5),
      full: screen - insets.top - Space.sm, // stops just below the notch / status bar
    };
  }, [height, reservedBelow, insets.top, insets.bottom]);
}

export function Sheet({ size, reservedBelow = 0, onSizeChange, header, children }: Props) {
  const colors = useColors();
  const insets = useSafeAreaInsets();
  const heights = useSheetHeights(reservedBelow);
  const [visible] = useState(() => new Animated.Value(heights[size]));
  const [drag] = useState(() => ({ start: 0 })); // height when the current drag began

  const settle = (to: SheetSize) =>
    Animated.spring(visible, { toValue: heights[to], useNativeDriver: false, bounciness: 0, speed: 16 }).start();

  useEffect(() => {
    settle(size);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size, heights]);

  const pan = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 4,
        onPanResponderGrant: () => {
          visible.stopAnimation((v) => {
            drag.start = v;
          });
        },
        onPanResponderMove: (_, g) => {
          const h = Math.min(heights.full, Math.max(heights.peek, drag.start - g.dy));
          visible.setValue(h);
        },
        onPanResponderRelease: (_, g) => {
          const projected = drag.start - g.dy - g.vy * 150;
          const order: SheetSize[] = ['peek', 'half', 'full'];
          const next = order.reduce((best, s) =>
            Math.abs(heights[s] - projected) < Math.abs(heights[best] - projected) ? s : best,
          );
          settle(next);
          onSizeChange(next);
        },
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [heights, onSizeChange],
  );

  const cycle = () => onSizeChange(size === 'peek' ? 'half' : size === 'half' ? 'full' : 'half');

  return (
    <Animated.View
      style={[
        styles.sheet,
        { height: visible, backgroundColor: colors.background, borderColor: colors.border },
      ]}>
      <View {...pan.panHandlers}>
        <Pressable onPress={cycle} accessibilityRole="adjustable" accessibilityLabel="Resize panel" style={styles.grab}>
          <View style={[styles.grabber, { backgroundColor: colors.border }]} />
        </Pressable>
        {header}
      </View>
      <ScrollView
        style={styles.body}
        contentContainerStyle={{ paddingHorizontal: Space.lg, paddingBottom: (reservedBelow ? 0 : insets.bottom) + Space.xl }}
        keyboardShouldPersistTaps="handled">
        {children}
      </ScrollView>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  sheet: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18,
    borderWidth: StyleSheet.hairlineWidth,
    shadowColor: '#000',
    shadowOpacity: 0.18,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: -2 },
    overflow: 'hidden',
  },
  grab: { alignItems: 'center', paddingVertical: Space.sm },
  grabber: { width: 40, height: 5, borderRadius: 3 },
  body: { flex: 1 },
});
