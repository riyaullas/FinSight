"use client";

import { Moon, Sun } from "lucide-react";
import { Button } from "./ui/primitives";

export function ThemeToggle() {
  function toggle() {
    const dark = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("theme", dark ? "dark" : "light");
    } catch {
      /* storage unavailable */
    }
  }
  return (
    <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle light or dark theme">
      <Sun className="hidden dark:block" />
      <Moon className="dark:hidden" />
    </Button>
  );
}
