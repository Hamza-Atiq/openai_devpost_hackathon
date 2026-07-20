"use client";

import { useEffect, useState } from "react";

const sections = [
  ["01", "Format and teams", "format-and-teams"],
  ["02", "Venues and location", "venues-and-location"],
  ["03", "Dates and slots", "dates-and-slots"],
  ["04", "Constraints", "constraints"],
] as const;

export function SetupSectionNav() {
  const [activeId, setActiveId] = useState<(typeof sections)[number][2]>(sections[0][2]);

  useEffect(() => {
    const ids = new Set(sections.map(([, , id]) => id));
    const hashId = window.location.hash.slice(1);
    if (ids.has(hashId as (typeof sections)[number][2])) {
      setActiveId(hashId as (typeof sections)[number][2]);
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort(
            (left, right) =>
              Math.abs(left.boundingClientRect.top) - Math.abs(right.boundingClientRect.top),
          );
        const nextId = visible[0]?.target.id;
        if (nextId && ids.has(nextId as (typeof sections)[number][2])) {
          setActiveId(nextId as (typeof sections)[number][2]);
        }
      },
      { rootMargin: "-20% 0px -65% 0px" },
    );

    sections.forEach(([, , id]) => {
      const target = document.getElementById(id);
      if (target) observer.observe(target);
    });
    return () => observer.disconnect();
  }, []);

  return (
    <ol className="setup-steps" aria-label="Setup sections">
      {sections.map(([number, label, id]) => (
        <li key={id}>
          <a
            href={`#${id}`}
            aria-current={activeId === id ? "location" : undefined}
            aria-label={`Go to ${label}`}
            onClick={() => setActiveId(id)}
          >
            <b>{number}</b>
            <span>{label}</span>
          </a>
        </li>
      ))}
    </ol>
  );
}
