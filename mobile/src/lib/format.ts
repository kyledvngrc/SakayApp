// Display formatting (pure functions).
import type { RiderType } from './types';

/** '120 m' (nearest 10 m) or '1.7 km'. Matches the back-end's wording. */
export function distanceText(m: number): string {
  return m < 950 ? `${Math.max(10, Math.round(m / 10) * 10)} m` : `${(m / 1000).toFixed(1)} km`;
}

export const peso = (amount: number) => `₱${amount.toFixed(2)}`;

export const RIDER_LABELS: Record<RiderType, string> = {
  regular: 'Regular',
  student: 'Student',
  senior: 'Senior',
  pwd: 'PWD',
};

/** Black or white text, whichever reads better on `hex`. */
export function textOn(hex: string): string {
  const n = parseInt(hex.replace('#', ''), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  return 0.299 * r + 0.587 * g + 0.114 * b > 160 ? '#111111' : '#ffffff';
}
