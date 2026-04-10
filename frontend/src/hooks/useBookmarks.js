// frontend/src/hooks/useBookmarks.js
import { useState, useEffect } from "react";

const STORAGE_KEY = "ahmedabad-jobs-bookmarks";

export default function useBookmarks() {
  const [bookmarks, setBookmarks] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return new Set(stored ? JSON.parse(stored) : []);
    } catch {
      return new Set();
    }
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...bookmarks]));
  }, [bookmarks]);

  function toggle(id) {
    setBookmarks((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function isBookmarked(id) {
    return bookmarks.has(id);
  }

  return { bookmarks, toggle, isBookmarked };
}
