# CogniGuard image-watermark Linux/GPU deployment bundle

This directory is a deployment recipe, not a deployment record. It prepares a
single-host or shared-filesystem Linux GPU run; no remote server was contacted
and no benchmark result is implied by these files.

## Runtime contract

The current API exchanges **filesystem paths**, not image bytes. The main
CogniGuard process, the SCE-LocGuard API, and the benchmark runner therefore
must see the checkout, input images, and output directories at identical
absolute paths. Configure `COGNIGUARD_SHARED_ROOT` and keep all three processes
on the same host or shared mount.

Run one Uvicorn worker only. Model objects and the JSON source registry are
process-local; multiple workers can duplicate GPU memory and split registry
state. The supplied launcher always uses `--workers 1`.

For a paper run, use fixed manifest splits and seeds and retain every run. Do
not repeat seeds until a favorable result appears. `SCE_LOCGUARD_DETERMINISTIC`
must be true, the server-side HMAC registry secret must be configured, and the
preflight report must have zero errors. The existing API is an EditGuard-based
wrapper; these deployment files do not turn unfinished DFG training stubs into
a trained algorithm.

The localization settings are frozen from the development split before any
reported test run: `SCE_LOCGUARD_RECOVERY_THRESHOLD=0.28` and
`SCE_LOCGUARD_TAMPER_AREA_THRESHOLD=0.001`. The raw predicted mask receives no
connected-component filtering. Changing either value creates a new experiment
configuration and requires a new run directory; it must never be selected from
test-set performance.

## 1. Copy source and non-Git assets

Copy the complete checkout, including `third_party/editguard/` and `protection/supporting/image_watermark/`. Checkpoints,
datasets, Hugging Face caches, and experiment outputs are intentionally ignored
by Git and need a separate, auditable transfer. Preserve the absolute shared
path used by every process.

The provided [`assets.manifest.example.json`](assets.manifest.example.json)
contains the hashes observed in the development workspace on 2026-08-02. After
copying, do not silently update a mismatch. Confirm the asset is intentionally
different, record its provenance, then create a reviewed manifest with the new
hash.

The AIGC path is offline at runtime. Pre-populate this exact cache marker below
`HF_HOME`:

```text
models--stable-diffusion-v1-5--stable-diffusion-inpainting/
  snapshots/<revision>/model_index.json
```

For a formal run, set `SCE_LOCGUARD_INPAINT_MODEL_REVISION` to the exact
snapshot commit directory name. When `--require-hf-cache` is active, the
preflight rejects an empty revision and rejects a value that does not match a
complete cached snapshot directory.

That snapshot must also contain `scheduler`, `text_encoder`, `tokenizer`,
`unet`, and `vae` directories. The launchers enforce Hugging Face offline mode,
so a missing file fails the run instead of being downloaded during an
experiment.

## 2. Create the Python environment

Use Python 3.10, 3.11, or 3.12. Select the CUDA-enabled PyTorch wheel compatible with
the target NVIDIA driver rather than copying a wheel choice from another
machine. One example for a host compatible with the CUDA 12.1 wheel is:

```bash
sudo apt-get update
sudo apt-get install -y git curl libgl1 libglib2.0-0
cd /shared/CogniGuard
python3.10 -m venv .venv-server
source .venv-server/bin/activate
python -m pip install --upgrade pip wheel setuptools
python -m pip install torch==2.4.1 torchvision==0.19.1 \
  --index-url https://download.pytorch.org/whl/cu121
python -m pip install -r protection/supporting/image_watermark/requirements.server.txt
python -m pip check
```

The requirements file is a compatibility envelope because the exact PyTorch
build depends on the server driver. Archive `python -m pip freeze` with every
formal run; the Slurm example does this automatically.

## 3. Configure paths and the secret

Use [`server.env.example`](server.env.example) as a checklist and store the real
environment file outside the repository. Generate a new random value rather
than reusing a sample:

```bash
install -d -m 700 /run/secrets
umask 077
python -c 'import secrets; print(secrets.token_hex(32))' \
  > /run/secrets/cogniguard_registry_secret
chmod 600 /run/secrets/cogniguard_registry_secret
```

Never commit, print, or place that value in a Slurm script. Keep the same secret
for all shards that must verify the same registered sources. Rotating it starts
a new authentication namespace and should be recorded as a new experiment.

## 4. Preflight and start one worker

Run the strict preflight before a formal benchmark:

```bash
export SERVER_ENV_FILE=/secure/cogniguard-watermark.env
set -a; source "$SERVER_ENV_FILE"; set +a
"$PYTHON_BIN" scripts/server/preflight_image_watermark.py \
  --project-root "$SCE_LOCGUARD_PROJECT_ROOT" \
  --shared-root "$COGNIGUARD_SHARED_ROOT" \
  --asset-manifest "$COGNIGUARD_WATERMARK_ASSET_MANIFEST" \
  --benchmark-config "$COGNIGUARD_WATERMARK_BENCHMARK_CONFIG" \
  --hf-cache "$HF_HOME" \
  --min-dataset-samples 500 --min-test-samples 500 \
  --min-source-datasets 2 \
  --min-content-domains 4 \
  --require-linux --require-cuda --require-secret --require-shared-root \
  --require-asset-hashes --require-hf-cache --require-dataset-files \
  --require-license-metadata --require-deterministic \
  --output-json /shared/CogniGuard/var/outputs/preflight.json
```

The data check expects the portable JSONL manifest fields `sample_id`,
`relative_path`, `split`, `source_dataset`, `domain`, `license_id`, and
`provenance`. Dataset roots come from the benchmark YAML `datasets` list. They
can be overridden with repeated `--dataset-root NAME=PATH` arguments or a
`COGNIGUARD_DATASET_ROOTS_JSON` object. Missing licenses, duplicate IDs, absent
test split, unresolved paths, missing files, checkpoint hash mismatches, CUDA
failure, or incomplete diffusion cache fail a strict run.

When `manifest.verify_hashes: true`, every JSONL row must also include a valid
`sha256`; the preflight re-hashes each referenced image before the job starts.
The Slurm example additionally requires at least 500 total rows, 500 test rows,
two source datasets, and four content domains. Lower thresholds are suitable
for a labeled smoke run, not for the reported full comparison.

Start the API:

```bash
SERVER_ENV_FILE=/secure/cogniguard-watermark.env \
  scripts/server/start_image_watermark_api.sh
curl --fail http://127.0.0.1:8010/health
curl --fail http://127.0.0.1:8010/api/v1/capabilities
```

The standalone API launcher does not require a benchmark dataset by default.
Set `REQUIRE_DATASET_MANIFEST=1` when the same launch must also gate on the YAML
dataset manifest; the Slurm paper job always performs that strict data gate.

Keep the API bound to `127.0.0.1` unless an authenticated reverse proxy and
network policy are added. The API accepts host filesystem paths and is not
designed as a public endpoint.

## 5. Run a direct pilot without Slurm

Use the pilot wrapper on a dedicated GPU server, or inside an already reserved
interactive GPU allocation. Never run it on a shared cluster login node. It
does not call `sbatch`; the `#SBATCH` lines in the shared lifecycle script are
comments when that script is invoked by Bash.

```bash
export SERVER_ENV_FILE=/secure/cogniguard-watermark.env
PILOT_MAX_SAMPLES=8 bash scripts/server/run_image_watermark_pilot.sh
```

The wrapper derives a run-local config with one fixed seed, at most eight test
images, four traditional attacks, and one real AIGC inpainting attack. It keeps
strict real-pipeline checks, the exact cached model revision requirement,
dataset hashes, a fresh API job directory, and a fresh source registry. Only
dataset roots actually represented by the manifest are retained in the pilot
config, so missing future comparison datasets do not block service bring-up.

Pilot artifacts are written under
`var/outputs/image_watermark_pilot/pilot_<UTC>_<pid>/` and carry
`run-class.txt = pilot_not_for_paper`. A pilot result is never eligible for the
paper tables, even if all technical checks pass. Use it only to verify the
environment and end-to-end pipeline before staging the complete formal data.

## 6. Submit the formal benchmark example

Review the `#SBATCH` resource lines, environment path, dataset minimum, and
benchmark YAML before submission. Then:

```bash
chmod +x scripts/server/start_image_watermark_api.sh
mkdir -p var/logs
export SERVER_ENV_FILE=/secure/cogniguard-watermark.env
sbatch --export=ALL scripts/server/image_watermark_benchmark.sbatch
```

Submit from the checkout root. Slurm opens `var/logs/slurm-<job>-<id>.out`
before the job starts, so create that directory before calling `sbatch`.
Python launchers keep bytecode under `var/cache/python`; set
`PYTHONPYCACHEPREFIX` to override that location.

The formal lifecycle script refuses a direct non-Slurm launch. Each submitted
run forcibly places API jobs and the source registry under its own `RUN_DIR`,
overriding any standalone paths from `SERVER_ENV_FILE`. Its exit trap stops the
API and snapshots the registry on success, failure, interruption, or preflight
rejection.

The enabled `editguard_wrapper.base_url` in the benchmark YAML must match
`http://$WATERMARK_API_HOST:$WATERMARK_API_PORT`; the job fails early on a
configuration mismatch.

The job runs preflight, archives its JSON report plus dependency, GPU, OS, Git,
declared-input hash, and source-registry snapshots, starts one local API worker,
saves health/capability responses, and invokes:

```bash
python -m protection.supporting.image_watermark.experiments.paper_benchmark \
  --config protection/supporting/image_watermark/configs/paper_benchmark.yaml \
  --output-dir <run>/benchmark
```

Set `BENCHMARK_RESUME=1` only to resume the same declared run. Do not use it to
alter the manifest, attack grid, model assets, or seed list in place. Submit a
new run directory whenever any of those inputs changes.
