// Where the running app lives. Start it first: make up, make api, make worker, make web.
export const APP_URL = process.env.APP_URL ?? "http://localhost:5173";
export const BACKEND_DIR = new URL("../../backend/", import.meta.url).pathname;
export const HEADLESS = process.env.HEADED !== "1";
