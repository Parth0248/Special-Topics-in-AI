# Special Topics in AI

Projects on applied AI systems — each one standalone, with its own dependencies, run
command, and demo.

## Projects

### [Agent Harness Engineering](agent-harness-engineering/)

The layer between a language model and the real world: what the model can see, what it
is allowed to do, and what happens when it does it. Three takes on that problem — a
harness built from nothing, a production harness extended with custom plugins, and a
harness pointed at automated research.

## Working with this repo

Secrets are read from a local `.env` at the repository root, which is never committed:

```sh
cp .env.example .env
```

Fill in your own keys, then follow the README inside whichever project you want to run.

## License

MIT. See [LICENSE](LICENSE).
