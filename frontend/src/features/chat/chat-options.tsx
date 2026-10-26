import { Info } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/** The three choices that decide how a chat answers (spec 0010): who answers (agent), what it
 *  searches (embedding) and which model. Rendered as one labelled form so the new-chat card and
 *  the composer's info popover show exactly the same thing. */
export type ChatOptionPickers = { agent: ReactNode; embedding: ReactNode; model: ReactNode };

export function ChatOptionsForm({ agent, embedding, model }: ChatOptionPickers) {
  const rows = [
    { label: "Agent", hint: "Who answers: system message and RAG strategy", control: agent },
    { label: "Embedding", hint: "Which index it searches (or none)", control: embedding },
    { label: "Model", hint: "Which LLM writes the answer", control: model },
  ];
  return (
    <div className="grid gap-4">
      {rows.map((r) => (
        // A group named after the row (not a <label>): the pickers already carry their own
        // aria-label, and wrapping a Radix trigger in a <label> would double-fire clicks.
        <div key={r.label} role="group" aria-label={r.label} className="grid gap-1.5">
          <div>
            <p className="text-sm font-medium">{r.label}</p>
            <p className="text-xs text-muted-foreground">{r.hint}</p>
          </div>
          {r.control}
        </div>
      ))}
    </div>
  );
}

/** A new chat starts here: pick the settings, then "Start chat" swaps this card for the
 *  composer. Defaults are pre-filled (the last chat's), so it is one click when nothing changes. */
export function ChatSetupCard({
  onStart,
  ...pickers
}: ChatOptionPickers & { onStart: () => void }) {
  return (
    <Card role="region" aria-label="Set up chat" className="w-full">
      <CardHeader>
        <CardTitle>Set up this chat</CardTitle>
        <CardDescription>
          Choose who answers, what it searches and which model it uses. You can change these later
          from the info button in the message bar.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-5">
        <ChatOptionsForm {...pickers} />
        <Button className="justify-self-end" onClick={onStart}>
          Start chat
        </Button>
      </CardContent>
    </Card>
  );
}

/** The info button in the composer: the same settings, tucked away so the bar stays one row. */
export function ChatOptionsButton(pickers: ChatOptionPickers) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Chat options"
          title="Chat options"
          className="size-8 rounded-lg text-muted-foreground"
        >
          <Info className="size-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(22rem,90vw)]">
        <ChatOptionsForm {...pickers} />
      </PopoverContent>
    </Popover>
  );
}
