// Hands the chosen trip from the Plan tab to the live trip screen.
import type { Trip } from './types';

let active: Trip | null = null;

export const activeTrip = {
  set: (trip: Trip) => {
    active = trip;
  },
  get: () => active,
  clear: () => {
    active = null;
  },
};
