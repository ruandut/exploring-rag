import { useEffect, useRef, useSyncExternalStore } from "react";

import { socket, type ServerEvent } from "@/lib/socket";

export function useSocketStatus() {
  return useSyncExternalStore(
    (cb) => socket.onStatus(cb),
    () => socket.status,
  );
}

/** Call `handler` for every server event. The latest handler is always used. */
export function useSocketEvents(handler: (event: ServerEvent) => void) {
  const ref = useRef(handler);
  useEffect(() => {
    ref.current = handler;
  });
  useEffect(() => socket.subscribe((e) => ref.current(e)), []);
}
