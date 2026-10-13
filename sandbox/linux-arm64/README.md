# Proposed Luna test dependency image

Status: **source recipe only; not built, installed, started or attested**.
The owner has authorized source work while independent backup/recovery remains
pending. Building this recipe requires separate approval for downloads and guest
dependency installation. This is not a candidate runner or an execution grant.

`Dockerfile` pins the official Linux ARM64 Python base by manifest digest.
`requirements.lock` pins 22 wheels by version and SHA-256. `environment.json`
records the base config, package URLs/hashes and recipe identities. No project,
candidate, database, credential or home directory belongs in this build context.
The ignore file permits only the Dockerfile, lock and ignore file.

After approval, use only `sandbox/linux-arm64` as the build context and target
`linux/arm64`. The download stage has network access to obtain the approved wheel
artifacts; the final install stage uses only those wheels with network disabled.
Do not provide build secrets, SSH forwarding or candidate-controlled arguments.
Hash pinning fixes artifact identity; it does not certify package safety.
The final process defaults to UID/GID 10001. Read-only root, network denial,
resource limits and input mounting still belong to a separately verified runner.

The resolved packages match versions in the existing passing Mac test environment,
including Starlette 1.7.0 rather than the newer untested 1.8.0 selected by an
unconstrained resolution. Linux wheels and Python 3.13.16 remain unexecuted.
The hash-required, wheels-only dry run resolved all 22 artifacts without installing
or importing them. A separate metadata check evaluated dependency markers for
Linux/aarch64/CPython 3.13.16 and found the locked dependency closure satisfied.
This is not evidence of a successful image build or guest tests.

## What remains before use

1. Approve and verify runtime setup after backup/recovery. Record the exact signed
   runtime release, executable identities and supported host configuration.
2. Approve the base/wheel downloads and build in the dedicated context. Record
   the resulting immutable image manifest/config digest, exact package inventory,
   recipe hashes and build outcome. Never use a mutable tag as execution authority.
3. Run trusted baseline tests inside that image under the intended resource limits.
4. Pin and preload the VM startup image and kernel as well as this application
   image. Verify that candidate-time operation cannot download missing artifacts.
5. Prove host-observed containment, resource cleanup and receipt integrity with
   synthetic attacks before permitting a real candidate. Bind all environment
   identities and the reviewed source-input fingerprint to a short-lived approval.

## Apple runtime investigation, 2026-10-13

Inspected release 1.5.0, source tree `d265d669ecae041bf338cb3b39c4118316d138f0`.
The release helper recognizes network `none`; an omitted network uses the default.
Creation obtains both the application and init images plus a kernel. Its image
fetch helper falls back to a registry pull when local content is missing. Guest
network denial therefore cannot certify host-side offline operation. A prior
local-cache check alone is insufficient evidence against removal/races. Runtime
adoption remains unapproved and unverified; do not enable candidate runs from
these flags alone.

References: [Apple creation helper](https://github.com/apple/container/blob/1.5.0/Sources/Services/ContainerAPIService/Client/Utility.swift),
[image fetch](https://github.com/apple/container/blob/1.5.0/Sources/Services/ContainerAPIService/Client/ClientImage.swift),
[network names](https://github.com/apple/container/blob/1.5.0/Sources/Services/ContainerAPIService/Client/NetworkClient.swift),
[pip hash requirements](https://pip.pypa.io/en/stable/topics/secure-installs/),
[Dockerfile semantics](https://docs.docker.com/reference/dockerfile/).
