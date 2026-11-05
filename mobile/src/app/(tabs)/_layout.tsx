import { Tabs } from 'expo-router/js-tabs';

import { Icon } from '@/components/icon';
import { useColors } from '@/constants/theme';

export default function TabsLayout() {
  const c = useColors();
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: c.accent,
        tabBarInactiveTintColor: c.textSecondary,
        tabBarStyle: { backgroundColor: c.background, borderTopColor: c.border },
      }}>
      <Tabs.Screen
        name="index"
        options={{ title: 'Plan', tabBarIcon: ({ color }) => <Icon name="map.fill" color={color} size={22} fallback="◇" /> }}
      />
      <Tabs.Screen
        name="routes"
        options={{ title: 'Routes', tabBarIcon: ({ color }) => <Icon name="bus.fill" color={color} size={22} fallback="≡" /> }}
      />
    </Tabs>
  );
}
