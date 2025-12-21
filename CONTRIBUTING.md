# Contributing to claude-usage

Thank you for your interest in contributing! This document covers the
guidelines and conventions used in this project.

## Before You Start

Reading through the existing code helps understand the patterns and
conventions in use. The main script has an extensive docstring (137 lines)
with ASCII diagrams explaining the layout system.

## Code Style

- Python 3.9+
- Type hints where they add clarity
- Tests for new functionality
- Comments that explain reasoning, not just mechanics

## Testing Requirements

### Running Tests

```bash
# Unit tests (32 tests covering formatters, calculations, layout)
python3 tests/test_claude_usage.py

# Layout validation at different widths
COLUMNS=69 ./src/claude_usage --check
COLUMNS=80 ./src/claude_usage --check
COLUMNS=86 ./src/claude_usage --check

# Overflow tests
./tests/test-usage.sh

# Golden comparison against HEAD
./tests/compare-versions.sh
```

All tests must pass before submitting a PR.

## Pull Requests

Good PRs typically:
- Solve a specific, well-defined problem
- Include tests for new code
- Don't break existing tests
- Have clear descriptions

---

## Technical Notes

*These details matter for anyone modifying the layout code.*

### Fixed-Width Formatters

The formatters produce exact character counts. This is a hard requirement.

```python
fmt_tok_fixed(309_500_000, 10)  # "309.5 Mtok" — exactly 10 chars
fmt_cost_fixed(464.22, 10)      # "464.22 USD" — exactly 10 chars
```

The layout calculations depend on these widths being consistent. Dynamic
sizing has been tried. It created more problems than it solved.

### Layout Validation

The `--check` mode runs alignment validation at the current terminal width.
If you modify layout code, run this at multiple widths (69, 80, 86) to
verify nothing breaks at the edge cases.

The validators check:
- Border integrity (no content clobbering box characters)
- Content bounds (nothing touching borders)
- Right-hand-side alignment (costs align to A6)

---

## Deeper Conventions

*This section exists for completeness. Most contributors won't need it.*

### Why Some Decisions Were Made

**Q: Why discrete breakpoints instead of continuous scaling?**
The math gets complicated. Discrete breakpoints let us validate specific
layouts rather than an infinite space of possibilities.

**Q: Why not refactor into multiple files?**
The single-file approach keeps deployment simple (copy one file) and makes
the control flow easy to follow. The tradeoff is a 1500-line file, but
it's well-organized with clear sections.

**Q: Why the extensive docstring?**
Experience suggests that without detailed documentation, the layout logic
becomes difficult to modify safely. The docstring serves as a specification
that the code should match.

### Common Pitfalls

Things that seem like improvements but historically haven't been:

- Adding "flexibility" to fixed-width formatters
- Refactoring the layout system mid-feature
- Changing spacing without running tests at all breakpoints
- "Quick fixes" that don't account for edge cases

### The Branch Graveyard

The `jaamesd/*` branches in the repository contain abandoned attempts at
changes that didn't work out. They're preserved as educational examples
of common failure modes:

- `jaamesd/sparkles` — Syntax errors from hasty changes
- `jaamesd/fix` — Merge conflict artifacts
- `jaamesd/cleanup` — Refactoring without tests
- `jaamesd/fast` — Premature optimization

These illustrate why the testing requirements exist.

---

## Questions

For questions about the code, open an issue with:
- What you're trying to understand or accomplish
- What you've already tried
- Relevant context (terminal width, Python version, etc.)

Specific questions get better answers.
