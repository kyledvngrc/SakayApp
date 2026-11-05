// Live trip: follows the commuter on the map and says when to get off.
import { router } from 'expo-router';
import { useKeepAwake } from 'expo-keep-awake';
import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Icon } from '@/components/icon';
import { RouteBadge } from '@/components/route-badge';
import { TripMap } from '@/components/trip-map';
import { TripSteps } from '@/components/trip-steps';
import { Space, useColors, type Colors } from '@/constants/theme';
import { useLiveTrip } from '@/hooks/use-live-trip';
import { activeTrip } from '@/lib/active-trip';
import { distanceText } from '@/lib/format';
import { headline } from '@/lib/live';
import type { Trip } from '@/lib/types';

export default function LiveScreen() {
  const [trip] = useState(() => activeTrip.get());
  if (!trip) {
    return <NoTrip />;
  }
  return <LiveTrip trip={trip} />;
}

function NoTrip() {
  const c = useColors();
  return (
    <View style={[styles(c).center, { backgroundColor: c.background }]}>
      <Text style={{ color: c.text, fontSize: 16 }}>No trip to follow.</Text>
      <Pressable onPress={() => router.back()} style={[styles(c).pill, { marginTop: Space.lg }]}>
        <Text style={styles(c).pillText}>Back</Text>
      </Pressable>
    </View>
  );
}

function LiveTrip({ trip }: { trip: Trip }) {
  useKeepAwake(); // Expo Go only gets GPS while the app is open, so keep the screen on
  const c = useColors();
  const s = styles(c);
  const insets = useSafeAreaInsets();
  const [soundOn, setSoundOn] = useState(true);
  const [follow, setFollow] = useState(true);
  const [showSteps, setShowSteps] = useState(false);
  const { live, gps, next, back } = useLiveTrip(trip, soundOn);

  const seg = trip.segments[live.step];
  const alert = seg.kind === 'ride' && (live.soonAlerted || live.hereAlerted) && !live.arrived;
  const end = () => {
    activeTrip.clear();
    router.back();
  };

  return (
    <View style={s.screen}>
      <TripMap
        trip={trip}
        origin={null}
        destination={null}
        bottomInset={140 + insets.bottom}
        topInset={190}
        followUser={follow}
        onUserPan={() => setFollow(false)}
      />

      {/* Top: what to do now */}
      <View style={[s.card, alert && s.cardAlert, { top: insets.top + Space.sm }]}>
        <View style={s.cardTop}>
          <Pressable onPress={end} hitSlop={10} accessibilityLabel="End trip">
            <Icon name="xmark" color={alert ? c.accentText : c.text} size={18} fallback="✕" />
          </Pressable>
          {seg.kind === 'ride' ? (
            <RouteBadge code={seg.route.code} color={seg.route.color} />
          ) : (
            <Icon name="figure.walk" color={alert ? c.accentText : c.walk} size={20} fallback="🚶" />
          )}
          <Text style={[s.step, alert && s.onAlert]}>
            Step {live.step + 1} of {trip.segments.length}
          </Text>
          <Pressable
            onPress={() => setSoundOn(!soundOn)}
            hitSlop={10}
            accessibilityLabel={soundOn ? 'Turn spoken alerts off' : 'Turn spoken alerts on'}>
            <Icon name={soundOn ? 'speaker.wave.2.fill' : 'speaker.slash.fill'} color={alert ? c.accentText : c.text} size={20} fallback={soundOn ? '🔊' : '🔇'} />
          </Pressable>
        </View>
        <Text style={[s.headline, alert && s.onAlert]} accessibilityLiveRegion="assertive">
          {headline(trip, live, distanceText)}
        </Text>
        {!live.arrived && <Text style={[s.instruction, alert && s.onAlert]}>{seg.instruction}</Text>}
        {live.offRoute && <Text style={s.warn}>You seem to be off the route. Check the map, or tap Next if you changed plans.</Text>}
        {gps === 'denied' && <Text style={s.warn}>Location is off. Allow it for SakayApp in Settings to get alerts.</Text>}
        {gps === 'error' && <Text style={s.warn}>Can’t read your location right now.</Text>}
        {gps === 'starting' && <Text style={s.muted}>Finding your location…</Text>}
        {live.weakGps && gps === 'tracking' && <Text style={s.muted}>Weak GPS signal; distances may lag.</Text>}
      </View>

      {!follow && (
        <Pressable onPress={() => setFollow(true)} style={[s.fab, { bottom: 140 + insets.bottom + Space.md }]} accessibilityLabel="Follow my location">
          <Icon name="location.fill" color={c.accent} fallback="◎" />
        </Pressable>
      )}

      {/* Bottom: step controls */}
      <View style={[s.bar, { paddingBottom: insets.bottom + Space.md }]}>
        {live.arrived ? (
          <Pressable onPress={end} style={[s.pill, s.wide]}>
            <Text style={s.pillText}>Done</Text>
          </Pressable>
        ) : (
          <>
            <Pressable onPress={back} disabled={live.step === 0} style={[s.secondary, live.step === 0 && { opacity: 0.4 }]} accessibilityLabel="Previous step">
              <Icon name="chevron.left" color={c.text} size={16} fallback="‹" />
            </Pressable>
            <Pressable onPress={() => setShowSteps(true)} style={[s.secondary, s.grow]}>
              <Text style={s.secondaryText}>All steps</Text>
            </Pressable>
            <Pressable onPress={next} style={[s.pill, s.grow]} accessibilityLabel="Next step">
              <Text style={s.pillText}>{live.step === trip.segments.length - 1 ? 'Arrived' : 'Next step'}</Text>
            </Pressable>
          </>
        )}
      </View>
      <Text style={[s.note, { bottom: insets.bottom + 76 }]}>Keep SakayApp open during the trip for alerts.</Text>

      <Modal visible={showSteps} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setShowSteps(false)}>
        <View style={[s.modal, { backgroundColor: c.background }]}>
          <View style={s.modalHead}>
            <Text style={s.modalTitle}>All steps</Text>
            <Pressable onPress={() => setShowSteps(false)} hitSlop={10}>
              <Text style={{ color: c.accent, fontSize: 16, fontWeight: '600' }}>Close</Text>
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={{ padding: Space.lg }}>
            <TripSteps trip={trip} />
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const styles = (c: Colors) =>
  StyleSheet.create({
    screen: { flex: 1, backgroundColor: c.background },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
    card: {
      position: 'absolute', left: Space.md, right: Space.md, backgroundColor: c.background, borderRadius: 16, padding: Space.lg,
      shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 10, shadowOffset: { width: 0, height: 3 },
    },
    cardAlert: { backgroundColor: c.accent },
    cardTop: { flexDirection: 'row', alignItems: 'center', gap: Space.md },
    step: { flex: 1, color: c.textSecondary, fontSize: 13, fontWeight: '600' },
    headline: { color: c.text, fontSize: 28, fontWeight: '800', marginTop: Space.md },
    instruction: { color: c.textSecondary, fontSize: 15, marginTop: Space.xs, lineHeight: 20 },
    onAlert: { color: c.accentText },
    warn: { backgroundColor: c.warnBg, color: c.warnText, borderRadius: 8, padding: Space.sm, marginTop: Space.sm, overflow: 'hidden' },
    muted: { color: c.textSecondary, fontSize: 13, marginTop: Space.sm },
    bar: {
      position: 'absolute', left: 0, right: 0, bottom: 0, flexDirection: 'row', gap: Space.sm, paddingHorizontal: Space.lg, paddingTop: Space.md,
      backgroundColor: c.background, borderTopLeftRadius: 18, borderTopRightRadius: 18,
    },
    note: { position: 'absolute', left: 0, right: 0, textAlign: 'center', color: c.textSecondary, fontSize: 12 },
    pill: { backgroundColor: c.accent, borderRadius: 24, paddingVertical: 14, paddingHorizontal: Space.xl, alignItems: 'center', justifyContent: 'center' },
    pillText: { color: c.accentText, fontSize: 16, fontWeight: '700' },
    secondary: { backgroundColor: c.surface, borderRadius: 24, paddingVertical: 14, paddingHorizontal: Space.lg, alignItems: 'center', justifyContent: 'center' },
    secondaryText: { color: c.text, fontSize: 16, fontWeight: '600' },
    grow: { flex: 1 },
    wide: { flex: 1 },
    fab: {
      position: 'absolute', right: Space.lg, width: 44, height: 44, borderRadius: 22, backgroundColor: c.background,
      alignItems: 'center', justifyContent: 'center', shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 6, shadowOffset: { width: 0, height: 2 },
    },
    modal: { flex: 1 },
    modalHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: Space.lg },
    modalTitle: { color: c.text, fontSize: 20, fontWeight: '700' },
  });
