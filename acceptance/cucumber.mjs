// Cucumber config. The specs in ../specs ARE the feature files ("Markdown with Gherkin"):
// prose sections are ignored, `# Feature:` / `## Scenario:` headings and `* Given/When/Then`
// bullets are executed.
//
// Only specs whose status is Approved, In progress or Done run — Drafts are still being
// written, so their steps may not exist yet. Pass explicit paths to run a draft anyway:
//   vp run test -- ../specs/0005-agents-and-chat.feature.md
import { readdirSync, readFileSync } from "node:fs";

const SPECS_DIR = "../specs";
const RUNNABLE = /^- \*\*Status:\*\*\s*(Approved|In progress|Done)\b/m;

const runnableSpecs = readdirSync(SPECS_DIR)
  .filter((f) => f.endsWith(".feature.md"))
  .filter((f) => RUNNABLE.test(readFileSync(`${SPECS_DIR}/${f}`, "utf8")))
  .map((f) => `${SPECS_DIR}/${f}`);

const explicitPaths = process.argv.slice(2).some((a) => a.endsWith(".md"));

export default {
  paths: explicitPaths ? [] : runnableSpecs,
  import: ["support/**/*.ts", "steps/**/*.ts"],
  format: ["progress-bar", "html:reports/acceptance.html", "summary"],
  // Undefined or pending steps fail the run: a spec isn't Done until every line executes.
  strict: true,
};
