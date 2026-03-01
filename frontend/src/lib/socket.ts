import { io, Socket } from "socket.io-client";
import { SOCKET_URL } from "@/lib/constants";

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    console.log("🔌 Initializing socket with URL:", SOCKET_URL);
    socket = io(SOCKET_URL, {
      autoConnect: false,
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });

    // Add connection debugging
    socket.on("connect", () => {
      console.log("✅ Socket connected:", socket?.id);
    });

    socket.on("connect_error", (error) => {
      console.error("❌ Socket connection error:", error);
    });

    socket.on("disconnect", (reason) => {
      console.warn("⏸️ Socket disconnected:", reason);
    });
  }
  return socket;
}

export function connectSocket(token?: string): Socket {
  const s = getSocket();
  if (token) {
    s.auth = { token };
  }
  if (!s.connected) {
    console.log("🔗 Connecting socket...");
    s.connect();
  }
  return s;
}

export function disconnectSocket(): void {
  if (socket?.connected) {
    console.log("🔌 Disconnecting socket");
    socket.disconnect();
  }
}
