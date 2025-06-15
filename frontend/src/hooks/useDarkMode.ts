'use client';

import { useEffect, useState } from 'react';

export function useDarkMode() {
    const [isDark, setIsDark] = useState(false);

useEffect(() => {
    // Check if there's a saved preference
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
    setIsDark(savedTheme === 'dark');
    } else {
      // Check system preference
    setIsDark(window.matchMedia('(prefers-color-scheme: dark)').matches);
    }
    }, []);

    useEffect(() => {
    // Apply the theme to the document
    if (isDark) {
    document.documentElement.classList.add('dark');
    localStorage.setItem('theme', 'dark');
    } else {
    document.documentElement.classList.remove('dark');
    localStorage.setItem('theme', 'light');
    }
    }, [isDark]);

    const toggleDarkMode = () => {
    setIsDark(!isDark);
    };

    return { isDark, toggleDarkMode };
} 