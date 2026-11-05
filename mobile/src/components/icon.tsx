// SF Symbols on iOS, with a text fallback elsewhere.
import { SymbolView, type SFSymbol } from 'expo-symbols';
import { Text, type ColorValue } from 'react-native';

type Props = { name: SFSymbol; color: ColorValue; size?: number; fallback?: string };

export function Icon({ name, color, size = 18, fallback = '•' }: Props) {
  return (
    <SymbolView
      name={name}
      tintColor={color}
      size={size}
      style={{ width: size, height: size }}
      fallback={<Text style={{ color, fontSize: size * 0.8 }}>{fallback}</Text>}
    />
  );
}
