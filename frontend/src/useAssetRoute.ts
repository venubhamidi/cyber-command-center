// Which asset the URL points at (?asset=EA-000003). The URL is the navigation state, so a link can be
// shared and the browser's back button returns to the inventory with its filters intact (ticket 08).
import { useEffect, useState } from "react";

function current(): string | null {
  return new URLSearchParams(window.location.search).get("asset");
}

export function useAssetRoute(): [string | null, (id: string | null) => void] {
  const [asset, setAsset] = useState<string | null>(current);
  useEffect(() => {
    const onPop = () => setAsset(current());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  function navigate(id: string | null) {
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("asset", id); else url.searchParams.delete("asset");
    window.history.pushState({}, "", url);
    setAsset(id);
  }
  return [asset, navigate];
}
