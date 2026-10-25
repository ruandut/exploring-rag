// Hand-drawn SVG so it themes with the app (Tailwind fill/stroke classes) and can be
// edited alongside content.ts when the architecture changes.

type Box = {
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  sub: string;
  planned?: boolean;
};

const BOXES: Record<string, Box> = {
  browser: { x: 20, y: 170, w: 150, h: 80, title: "Browser", sub: "React SPA (Vite+)" },
  api: { x: 250, y: 50, w: 190, h: 80, title: "Django API", sub: "DRF · SimpleJWT" },
  gateway: { x: 250, y: 290, w: 190, h: 80, title: "Channels", sub: "websocket gateway" },
  postgres: { x: 520, y: 20, w: 170, h: 80, title: "Postgres", sub: "pgvector · rag + hatchet" },
  hatchet: {
    x: 520,
    y: 170,
    w: 170,
    h: 80,
    title: "Hatchet engine",
    sub: "queue · cron · streams",
  },
  redis: { x: 520, y: 320, w: 170, h: 80, title: "Redis", sub: "channel layer only" },
  worker: { x: 740, y: 170, w: 140, h: 80, title: "Worker", sub: "Hatchet tasks (Django)" },
  llm: {
    x: 740,
    y: 20,
    w: 140,
    h: 80,
    title: "LLM provider",
    sub: "OpenAI-compat · Ollama",
  },
};

type Edge = {
  d: string;
  label: string;
  lx: number;
  ly: number;
  anchor?: "start" | "middle" | "end";
  both?: boolean;
};

const EDGES: Edge[] = [
  { d: "M170 195 L250 105", label: "REST + JWT", lx: 196, ly: 140, anchor: "end" },
  { d: "M170 225 L250 315", label: "WebSocket", lx: 196, ly: 285, anchor: "end", both: true },
  { d: "M440 80 L520 62", label: "ORM", lx: 480, ly: 62 },
  { d: "M440 110 L520 192", label: "start run", lx: 492, ly: 140, anchor: "start" },
  { d: "M440 310 L520 232", label: "run + subscribe", lx: 492, ly: 290, anchor: "start" },
  { d: "M605 170 L605 100", label: "state", lx: 611, ly: 140, anchor: "start" },
  { d: "M690 210 L740 210", label: "gRPC", lx: 715, ly: 202, both: true },
  { d: "M810 170 L810 100", label: "HTTPS", lx: 816, ly: 140, anchor: "start" },
  { d: "M752 170 L690 88", label: "vectors", lx: 714, ly: 120, anchor: "end" },
  { d: "M775 250 L690 352", label: "progress", lx: 738, ly: 312, anchor: "start" },
  { d: "M520 362 L440 345", label: "group_send", lx: 480, ly: 340 },
];

export function ArchitectureDiagram() {
  return (
    <div className="overflow-x-auto">
      <svg
        viewBox="0 0 900 420"
        className="min-w-[720px] text-muted-foreground"
        role="img"
        aria-label="Architecture: browser talks REST to Django API and WebSocket to Channels; API and Channels start Hatchet runs; the worker executes tasks, calls the LLM, writes vectors to Postgres, and sends progress through Redis back to Channels."
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M0 0 L10 5 L0 10 z" className="fill-muted-foreground" />
          </marker>
        </defs>

        {EDGES.map((e) => (
          <g key={e.d}>
            <path
              d={e.d}
              className="fill-none stroke-muted-foreground"
              strokeWidth={1.5}
              markerEnd="url(#arrow)"
              markerStart={e.both ? "url(#arrow)" : undefined}
            />
            <text
              x={e.lx}
              y={e.ly}
              textAnchor={e.anchor ?? "middle"}
              className="fill-muted-foreground text-[11px]"
            >
              {e.label}
            </text>
          </g>
        ))}

        {Object.entries(BOXES).map(([key, b]) => (
          <g key={key}>
            <rect
              x={b.x}
              y={b.y}
              width={b.w}
              height={b.h}
              rx={10}
              className="fill-card stroke-border"
              strokeWidth={1.5}
              strokeDasharray={b.planned ? "6 4" : undefined}
            />
            <text
              x={b.x + b.w / 2}
              y={b.y + 36}
              textAnchor="middle"
              className="fill-foreground text-[14px] font-semibold"
            >
              {b.title}
            </text>
            <text
              x={b.x + b.w / 2}
              y={b.y + 56}
              textAnchor="middle"
              className="fill-muted-foreground text-[11px]"
            >
              {b.sub}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
