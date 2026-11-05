// SakayApp colors (own palette, light and dark).
import { useColorScheme } from 'react-native';

type ColorKey =
  | 'text' | 'textSecondary' | 'background' | 'surface' | 'border' | 'accent' | 'accentText'
  | 'warnBg' | 'warnText' | 'walk' | 'start' | 'end';
export type Colors = Record<ColorKey, string>;

export const Palette: Record<'light' | 'dark', Colors> = {
  light: {
    text: '#1C2430',
    textSecondary: '#5E6875',
    background: '#FFFFFF',
    surface: '#F3F5F7',
    border: '#DDE2E8',
    accent: '#0B7A5B',
    accentText: '#FFFFFF',
    warnBg: '#FFF4D6',
    warnText: '#6D4B00',
    walk: '#5E6875',
    start: '#2E7D32',
    end: '#C62828',
  },
  dark: {
    text: '#E6EAEF',
    textSecondary: '#97A3B0',
    background: '#151A20',
    surface: '#202730',
    border: '#2E3742',
    accent: '#2FBF8F',
    accentText: '#0B1A14',
    warnBg: '#3A2F12',
    warnText: '#F3D48A',
    walk: '#B4BEC9',
    start: '#66BB6A',
    end: '#EF5350',
  },
};

export function useColors(): Colors {
  return Palette[useColorScheme() === 'dark' ? 'dark' : 'light'];
}

export const Space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 } as const;
