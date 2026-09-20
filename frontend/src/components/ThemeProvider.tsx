"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

type Theme = "dark" | "light";

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme | string) => void;
  resolvedTheme: Theme;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: "dark",
  setTheme: () => {},
  resolvedTheme: "dark",
});

interface ThemeProviderProps {
  children: React.ReactNode;
  attribute?: string;
  defaultTheme?: string;
  enableSystem?: boolean;
  storageKey?: string;
  [key: string]: any;
}

export function ThemeProvider({
  children,
  defaultTheme = "dark",
  storageKey = "theme",
}: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>((defaultTheme as Theme) || "dark");

  useEffect(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      const initialTheme = stored === "light" ? "light" : "dark";
      setThemeState(initialTheme);
      applyTheme(initialTheme);
    } catch {
      applyTheme((defaultTheme as Theme) || "dark");
    }
  }, [defaultTheme, storageKey]);

  function applyTheme(targetTheme: Theme) {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    if (targetTheme === "dark") {
      root.classList.add("dark");
      root.classList.remove("light");
    } else {
      root.classList.add("light");
      root.classList.remove("dark");
    }
  }

  function setTheme(newTheme: Theme | string) {
    const validTheme: Theme = newTheme === "light" ? "light" : "dark";
    setThemeState(validTheme);
    try {
      localStorage.setItem(storageKey, validTheme);
    } catch {}
    applyTheme(validTheme);
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme, resolvedTheme: theme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}

