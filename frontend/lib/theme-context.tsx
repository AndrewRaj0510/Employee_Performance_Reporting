"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export type ThemeMode = "system" | "light" | "dark";

interface ThemeContextValue {
    theme: ThemeMode;
    setTheme: (t: ThemeMode) => void;
    /** The resolved theme actually applied to the DOM ("light" | "dark") */
    resolved: "light" | "dark";
}

const ThemeContext = createContext<ThemeContextValue>({
    theme: "system",
    setTheme: () => {},
    resolved: "dark",
});

export function useTheme() {
    return useContext(ThemeContext);
}

function getSystemPreference(): "light" | "dark" {
    if (typeof window === "undefined") return "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    const [theme, setThemeState] = useState<ThemeMode>("system");
    const [resolved, setResolved] = useState<"light" | "dark">("dark");

    // Load persisted theme on mount
    useEffect(() => {
        const saved = (localStorage.getItem("hr-theme") as ThemeMode) ?? "system";
        setThemeState(saved);
    }, []);

    // Apply theme class to <html> and persist
    useEffect(() => {
        const applyTheme = (mode: ThemeMode) => {
            const actual = mode === "system" ? getSystemPreference() : mode;
            setResolved(actual);
            const root = document.documentElement;
            root.classList.remove("light", "dark");
            root.classList.add(actual);
            root.style.colorScheme = actual;
        };

        applyTheme(theme);

        // Re-apply when system preference changes (only relevant when theme === "system")
        const mq = window.matchMedia("(prefers-color-scheme: dark)");
        const handler = () => {
            if (theme === "system") applyTheme("system");
        };
        mq.addEventListener("change", handler);
        return () => mq.removeEventListener("change", handler);
    }, [theme]);

    const setTheme = (t: ThemeMode) => {
        setThemeState(t);
        localStorage.setItem("hr-theme", t);
    };

    return (
        <ThemeContext.Provider value={{ theme, setTheme, resolved }}>
            {children}
        </ThemeContext.Provider>
    );
}
