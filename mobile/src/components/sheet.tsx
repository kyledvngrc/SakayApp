// A draggable bottom sheet over the map: peek, half or full height.
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Animated, PanResponder, Pressable, ScrollView, StyleSheet, useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Space, useColors } from '@/constants/theme';

export type SheetSize = 'peek' | 'half' | 'full';

type Props = {
  size: SheetSize;
  bottomOffset?: number; // e.g. the tab bar's height
  onSizeChange: (size: SheetSize) => void;
  header?: ReactNode; // stays visible; dragging it moves the sheet
  children?: ReactNode; // scrolls
};

/** Visible sheet heights, measured above `bottomOffset`. */
export function useSheetHeights(bottomOffset = 0) {
  const { height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const below = bottomOffset || insets.bottom;
  return useMemo(
    () => ({
      peek: 150 + (bottomOffset ? 0 : insets.bottom),
      half: Math.round(height * 0.48) - (bottomOffset ? below : 0),
      full: Math.round(height - insets.top - 24 - (bottomOffset ? below : 0)),
    }),
    [height, insets.bottom, insets.top, bottomOffset, below],
  );
}

export function Sheet({ size, bottomOffset = 0, onSizeChange, header, children }: Props) {
  const colors = useColors();
  const insets = useSafeAreaInsets();
  const heights = useSheetHeights(bottomOffset);
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
        { height: visible, bottom: bottomOffset, backgroundColor: colors.background, borderColor: colors.border },
      ]}>
      <View {...pan.panHandlers}>
        <Pressable onPress={cycle} accessibilityRole="adjustable" accessibilityLabel="Resize panel" style={styles.grab}>
          <View style={[styles.grabber, { backgroundColor: colors.border }]} />
        </Pressable>
        {header}
      </View>
      <ScrollView
        style={styles.body}
        contentContainerStyle={{ paddingHorizontal: Space.lg, paddingBottom: (bottomOffset ? 0 : insets.bottom) + Space.xl }}
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
