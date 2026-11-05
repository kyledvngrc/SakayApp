// Full-screen map. Shows only the chosen trip (no other routes), plus start and end pins.
import { forwardRef } from 'react';
import { StyleSheet } from 'react-native';
import MapView, { Marker, Polyline, type LongPressEvent, type Region } from 'react-native-maps';

import { useColors } from '@/constants/theme';
import { DAVAO, toCoord } from '@/lib/geo';
import type { Endpoint, LatLng, Trip } from '@/lib/types';

type Props = {
  trip: Trip | null;
  origin: Endpoint | null;
  destination: Endpoint | null;
  bottomInset: number;
  topInset?: number;
  followUser?: boolean; // keep the map centred on the commuter (live trip)
  onUserPan?: () => void;
  onLongPress?: (p: LatLng) => void;
  onRegionChangeComplete?: (center: LatLng) => void;
};

export const TripMap = forwardRef<MapView, Props>(function TripMap(
  { trip, origin, destination, bottomInset, topInset = 0, followUser, onUserPan, onLongPress, onRegionChangeComplete },
  ref,
) {
  const c = useColors();
  return (
    <MapView
      ref={ref}
      style={StyleSheet.absoluteFill}
      initialRegion={DAVAO}
      showsUserLocation
      showsMyLocationButton={false}
      showsPointsOfInterests
      followsUserLocation={followUser}
      onPanDrag={onUserPan}
      mapPadding={{ top: topInset, left: 0, right: 0, bottom: bottomInset }}
      onLongPress={(e: LongPressEvent) =>
        onLongPress?.({ lat: e.nativeEvent.coordinate.latitude, lng: e.nativeEvent.coordinate.longitude })
      }
      onRegionChangeComplete={(r: Region) => onRegionChangeComplete?.({ lat: r.latitude, lng: r.longitude })}>
      {trip?.segments.map((s, i) =>
        s.kind === 'walk' ? (
          <Polyline key={`s${i}`} coordinates={s.path.map(toCoord)} strokeColor={c.walk} strokeWidth={4} lineDashPattern={[2, 8]} />
        ) : (
          <Polyline key={`s${i}`} coordinates={s.path.map(toCoord)} strokeColor={s.route.color} strokeWidth={7} />
        ),
      )}
      {trip?.segments.flatMap((s, i) =>
        s.kind === 'ride'
          ? [
              <Marker key={`b${i}`} coordinate={toCoord(s.board)} pinColor={s.route.color} title={`Get on ${s.route.code}`}
                description={s.board.place.name ? `${s.board.place.kind} ${s.board.place.name}` : undefined} />,
              <Marker key={`a${i}`} coordinate={toCoord(s.alight)} pinColor={s.route.color} title={`Get off ${s.route.code}`}
                description={s.alight.place.name ? `${s.alight.place.kind} ${s.alight.place.name}` : undefined} />,
            ]
          : [],
      )}

      {origin && !origin.isMyLocation && <Marker coordinate={toCoord(origin.point)} pinColor={c.start} title="Start" description={origin.label} />}
      {destination && <Marker coordinate={toCoord(destination.point)} pinColor={c.end} title="Destination" description={destination.label} />}
    </MapView>
  );
});
