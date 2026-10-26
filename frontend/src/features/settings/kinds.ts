/** Which API an endpoint speaks (spec 0008). Shared by the chat provider and connections. */
export type ProviderKind = "openai" | "anthropic" | "google";

export const KINDS: { value: ProviderKind; label: string; hint: string }[] = [
  {
    value: "openai",
    label: "OpenAI-compatible",
    hint: "OpenAI, OpenRouter, Ollama, vLLM, Groq… — needs a base URL.",
  },
  {
    value: "anthropic",
    label: "Anthropic",
    hint: "Claude, through Anthropic's own API. No embeddings — use another endpoint for those.",
  },
  {
    value: "google",
    label: "Google",
    hint: "Gemini, through Google's own API. Chat and embeddings.",
  },
];

/** Only OpenAI-compatible endpoints need a URL; the others default to their own API. */
export const needsBaseUrl = (kind: ProviderKind) => kind === "openai";

export const kindLabel = (kind: ProviderKind) => KINDS.find((k) => k.value === kind)?.label ?? kind;

export type Preset = { name: string; kind: ProviderKind; base_url: string; chat: string };

export const PRESETS: Preset[] = [
  { name: "OpenAI", kind: "openai", base_url: "https://api.openai.com/v1", chat: "gpt-5-mini" },
  {
    name: "OpenRouter",
    kind: "openai",
    base_url: "https://openrouter.ai/api/v1",
    chat: "openai/gpt-5-mini",
  },
  { name: "Ollama (local)", kind: "openai", base_url: "http://localhost:11434/v1", chat: "" },
  { name: "Anthropic", kind: "anthropic", base_url: "", chat: "claude-opus-5-5" },
  { name: "Google", kind: "google", base_url: "", chat: "gemini-2.5-flash" },
];
