// Step 2: business name / type / expected monthly volume.
import { BUSINESS_TYPE_OPTIONS } from "../../lib/submission";
import { Field, SelectField } from "./Field";

export default function BusinessStep({ submission, fieldsDisabled, setField }) {
  return (
    <>
      <Field label="Business name"
        value={submission.business_name}
        disabled={fieldsDisabled}
        onChange={(v) => setField("business_name", v)} />
      <SelectField label="Business type"
        value={submission.business_type}
        disabled={fieldsDisabled}
        options={BUSINESS_TYPE_OPTIONS}
        onChange={(v) => setField("business_type", v)} />
      <Field label="Expected monthly volume (USD)" type="number"
        value={submission.expected_monthly_volume_usd}
        disabled={fieldsDisabled}
        onChange={(v) => setField("expected_monthly_volume_usd", Number(v) || 0)} />
    </>
  );
}
