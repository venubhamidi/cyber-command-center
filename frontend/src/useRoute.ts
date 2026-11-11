// The URL is the navigation state (?view=assets&asset=EA-000003&criticality=critical), so a link can
// be shared and the browser's back button returns to where the user was (asset detail ticket 08).
import { useEffect, useState } from "react";

export type Route = Record<string, string>;

function current(): Route {
  return Object.fromEntries(new URLSearchParams(window.location.search));
}

export function useRoute(): [Route, (next: Route) => void] {
  const [route, setRoute] = useState<Route>(current);
  useEffect(() => {
    const onPop = () => setRoute(current());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  function go(next: Route) {
    const url = new URL(window.location.href);
    url.search = new URLSearchParams(next).toString();
    window.history.pushState({}, "", url);
    setRoute(next);
  }
  return [route, go];
}

// Turn a drill-down path from the API ("/?view=findings") into a route.
export function routeOf(path: string): Route {
  return Object.fromEntries(new URL(path, window.location.origin).searchParams);
}
