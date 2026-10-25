import type { Locator, Page } from "playwright";

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** The searchable model picker (spec 0010): a combobox named after its field that opens a
 *  list of the endpoint's models, grouped by kind, with "Use “…”" for any other id. */
export class ModelPicker {
  page: Page;
  label: string;

  constructor(page: Page, label: string) {
    this.page = page;
    this.label = label;
  }

  get trigger(): Locator {
    return this.page.getByRole("combobox", { name: this.label, exact: true });
  }

  /** The open list (cmdk renders it as a listbox). */
  get list(): Locator {
    return this.page.getByRole("listbox");
  }

  /** The option for a model id (badges may follow it). Never the chat's "<model> (default)"
   *  item, which stands for "the provider's chat model" rather than that id. */
  option(model: string, within?: Locator): Locator {
    const name = new RegExp(`^${escape(model)}(?! \\(default\\))(\\s|$)`);
    return (within ?? this.list).getByRole("option", { name });
  }

  group(name: string): Locator {
    return this.list.getByRole("group", { name, exact: true });
  }

  async open(): Promise<void> {
    await this.trigger.click();
    await this.page.getByRole("combobox", { name: `Search ${this.label}` }).waitFor();
  }

  async search(text: string): Promise<void> {
    await this.page.getByRole("combobox", { name: `Search ${this.label}` }).fill(text);
  }

  /** Pick a model: the listed one if the endpoint offers it, otherwise "Use “…”". */
  async pick(model: string): Promise<void> {
    await this.open();
    await this.search(model);
    const listed = this.option(model);
    const custom = this.page.getByRole("button", { name: `Use “${model}”` });
    await listed.or(custom).first().waitFor();
    // Give the list a moment to load before falling back to a custom id.
    await listed.waitFor({ timeout: 2_000 }).catch(() => undefined);
    if (await listed.count()) await listed.first().click();
    else await custom.click();
    await this.trigger.getByText(model, { exact: true }).waitFor();
  }
}
