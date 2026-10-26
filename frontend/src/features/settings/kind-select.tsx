import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { KINDS, type ProviderKind } from "./kinds";
import { Field } from "./provider-form";

/** The "Provider type" picker, used by the chat provider and by connections. */
export function KindSelect({
  id,
  label = "Provider type",
  value,
  onChange,
}: {
  id: string;
  label?: string;
  value: ProviderKind;
  onChange: (kind: ProviderKind) => void;
}) {
  return (
    <Field id={id} label={label} hint={KINDS.find((k) => k.value === value)?.hint}>
      <Select value={value} onValueChange={(v) => onChange(v as ProviderKind)}>
        <SelectTrigger id={id} className="w-full sm:w-72">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {KINDS.map((k) => (
            <SelectItem key={k.value} value={k.value}>
              {k.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
}
