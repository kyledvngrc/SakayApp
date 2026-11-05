// Shapes returned by the SakayApp API (backend/app/models.py, routers/).

export type LatLng = { lat: number; lng: number };
export type RiderType = 'regular' | 'student' | 'senior' | 'pwd';

export type Place = { kind: 'at' | 'near' | 'none'; name: string | null };

export type RouteInfo = {
  code: string;
  name: string;
  color: string;
  vehicle_type: string;
  is_bidirectional: boolean;
  kind: 'both' | 'oneway' | 'loop';
  length_km: number;
  path_geojson: { type: 'LineString'; coordinates: [number, number][] };
};

export type NearbyRoute = {
  code: string;
  name: string;
  color: string;
  kind: RouteInfo['kind'];
  walk_m: number;
  catch_at: LatLng;
};

export type Landmark = { id: number; name: string; description: string | null; lat: number; lng: number };

export type WalkSegment = {
  kind: 'walk';
  from: string;
  to: string;
  distance_m: number;
  path: LatLng[];
  instruction: string;
};

export type RideEnd = LatLng & { along_m: number; place: Place };

export type RideSegment = {
  kind: 'ride';
  route: { code: string; name: string; color: string; vehicle_type: string };
  heading: string | null;
  board: RideEnd;
  alight: RideEnd;
  distance_km: number;
  fare: number | null;
  path: LatLng[];
  instruction: string;
};

export type Segment = WalkSegment | RideSegment;

export type Trip = {
  route_codes: string[];
  transfers: number;
  ride_km: number;
  walking_m: number;
  total_fare: number | null;
  fare_available: boolean;
  segments: Segment[];
};

export type PlanResponse = {
  trips: Trip[];
  notice: string | null;
  rider_type: RiderType;
  fare_source: string | null;
  estimates_note: string;
};

/** A start or end point chosen by the commuter. */
export type Endpoint = { label: string; point: LatLng; isMyLocation?: boolean };
