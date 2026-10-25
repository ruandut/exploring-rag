// The spec list is read from ../specs at build time, so this page can't drift from the files.
const files = import.meta.glob("../../../../specs/[0-9]*.md", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

export type SpecInfo = {
  id: string;
  title: string;
  status: string;
  file: string;
  executable: boolean;
  scenarios: number;
};

export const SPECS: SpecInfo[] = Object.entries(files)
  .map(([path, text]) => {
    const file = path.split("/").pop()!;
    const heading = text.match(/^# (\d{4}) — (.+)$/m);
    return {
      id: heading?.[1] ?? file.slice(0, 4),
      title: heading?.[2] ?? file,
      status: text.match(/^- \*\*Status:\*\*\s*([A-Za-z ]+?)\s*(?:←|$)/m)?.[1] ?? "Unknown",
      file,
      executable: file.endsWith(".feature.md"),
      scenarios: (text.match(/^## Scenario( Outline)?:/gm) ?? []).length,
    };
  })
  .sort((a, b) => a.id.localeCompare(b.id));
