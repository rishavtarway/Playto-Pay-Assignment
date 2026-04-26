// Step 1: name / email / phone.
import { Field } from "./Field";

export default function PersonalStep({ submission, fieldsDisabled, setField }) {
  return (
    <>
      <Field label="Full name"
        value={submission.full_name}
        disabled={fieldsDisabled}
        onChange={(v) => setField("full_name", v)} />
      <Field label="Email" type="email"
        value={submission.email}
        disabled={fieldsDisabled}
        onChange={(v) => setField("email", v)} />
      <Field label="Phone"
        value={submission.phone}
        disabled={fieldsDisabled}
        onChange={(v) => setField("phone", v)} />
    </>
  );
}
