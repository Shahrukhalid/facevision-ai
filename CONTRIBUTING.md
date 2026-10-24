# Contributing

Thanks for helping improve FaceVision AI. Bug reports, documentation fixes, tests and evaluations are all welcome.

## Before you start

- Read the ground rules in [docs/DEVELOPER.md](docs/DEVELOPER.md#ground-rules-for-contributions). Pull requests that add telemetry, cloud processing, covert monitoring, identification against external sources or inference of sensitive traits will not be accepted.
- For larger changes, open an issue first to discuss the approach.

## Workflow

1. Fork the repository and create a branch.
2. Set up the development environment as described in [docs/DEVELOPER.md](docs/DEVELOPER.md).
3. Make your change, with tests.
4. Run `ruff check facevision tests tools`, `pytest`, and in `frontend/` `npm test` and `npx tsc --noEmit`.
5. Open a pull request describing what changed, why, and how you tested it.

## Never commit

- Photos or videos of real people (tests use generated images and scikit-image's public-domain sample portrait).
- Face templates, embeddings, databases or anything from your data folder.
- Model weight files (they are downloaded and verified by the Model Manager).
- `.env` files, passphrases, API keys or tokens.

## Adding a model

Follow [docs/MODELS.md](docs/MODELS.md#adding-or-replacing-a-model). Include its licence, upstream source, SHA-256 and any published evaluation. If its licence restricts commercial use, it must be opt-in and marked `research_only`.

## Evaluations

Results on lawfully obtained, consented datasets are especially valuable, particularly per-group error rates. Share the command you ran, the dataset description and licence, and the JSON report. Do not share the images.
