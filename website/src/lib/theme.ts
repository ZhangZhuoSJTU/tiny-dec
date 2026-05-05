import { createContext, useContext } from "react";

export const FONTS = {
  light: {
    display: '"Quicksand", sans-serif',
    body: '"Nunito", sans-serif',
    mono: '"Fira Code", ui-monospace, monospace',
  },
  dark: {
    display: '"Syne", sans-serif',
    body: '"DM Sans", sans-serif',
    mono: '"Fira Code", ui-monospace, monospace',
  },
} as const;

export type ThemeMode = "light" | "dark";
export type ThemeFonts = (typeof FONTS)["light"];

export function fontsFor(theme: ThemeMode) {
  return FONTS[theme];
}

export const ThemeContext = createContext<ThemeMode>("light");

export function useThemeFonts(): ThemeFonts {
  const theme = useContext(ThemeContext);
  return FONTS[theme];
}
