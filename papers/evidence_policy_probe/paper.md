# Internal Evidence-Policy Probe

This package is a synthetic validation harness, not a scientific paper reproduction target.

Its only purpose is to exercise the SciReplicBench scorer in a real Inspect run after the
task-level artifact-presence precheck has already passed. The probe contains two samples:

- `evidence_policy_probe_prose_fail`: a submission with non-trivial Python code, but passing
  evidence is still sourced from README-style prose, a bare output path, and a submission-side
  metric claim.
- `evidence_policy_probe_control_pass`: the matching control where the quoted evidence lives in
  the correct non-README submission and output files.

This harness exists so reviewers can see a benchmark-visible `.eval` log where
`evidence_policy_failed` activates without spending production-model budget or relying on the
public `squidpy_spatial` agents to clear precheck.
