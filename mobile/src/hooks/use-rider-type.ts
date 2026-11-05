// The rider type (for fare discounts), remembered on the device.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';

import type { RiderType } from '@/lib/types';

const KEY = 'sakay.riderType';
const VALID: RiderType[] = ['regular', 'student', 'senior', 'pwd'];

export function useRiderType() {
  const [rider, setRider] = useState<RiderType>('regular');

  useEffect(() => {
    AsyncStorage.getItem(KEY)
      .then((v) => {
        if (v && (VALID as string[]).includes(v)) setRider(v as RiderType);
      })
      .catch(() => {});
  }, []);

  const choose = (next: RiderType) => {
    setRider(next);
    AsyncStorage.setItem(KEY, next).catch(() => {});
  };

  return [rider, choose] as const;
}
