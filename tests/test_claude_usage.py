#!/usr/bin/env python3
"""Unit tests for claude-usage formatting and calculation functions.

Since claude-usage has module-level side effects (JSONL parsing, credentials),
we duplicate the pure functions here for isolated testing. This ensures:
1. Tests run fast without I/O
2. Tests validate the exact logic used in production
3. Any function changes must be reflected here (acts as a spec)

Run: python3 test_claude_usage.py
"""

import unittest
import subprocess
import os
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TOOL = SCRIPT_DIR.parent / "src" / "claude_usage"


# ============================================================================
# DUPLICATED PURE FUNCTIONS (from claude-usage)
# Keep in sync with the main script - any divergence is a test failure signal
# ============================================================================

def fmt_tok_fixed(n, width=10):
    """Format token count in exactly `width` chars, right-aligned.

    Always uses 1 decimal place and K/M/G/T tok units for consistency.
    """
    if n >= 1_000_000_000_000:
        num = f"{n/1_000_000_000_000:.1f}"
        unit = " Ttok"
    elif n >= 1_000_000_000:
        num = f"{n/1_000_000_000:.1f}"
        unit = " Gtok"
    elif n >= 1_000_000:
        num = f"{n/1_000_000:.1f}"
        unit = " Mtok"
    else:
        num = f"{n/1_000:.1f}"
        unit = " Ktok"
    num_width = width - len(unit)
    return f"{num:>{num_width}}{unit}"


def fmt_cost_fixed(c, width=10):
    """Format cost in exactly `width` chars, right-aligned with USD suffix."""
    num_width = width - 4  # " USD" is 4 chars
    return f"{c:>{num_width}.2f} USD"


def fmt_usd(amount):
    """Format USD amount with commas, no trailing zeros."""
    if amount >= 1000:
        return f"{amount:,.2f} USD"
    else:
        return f"{amount:.2f} USD"


# Pricing per million tokens (must match claude-usage PRICING dict)
PRICING = {
    "opus-4-5":   {"input": 5.0,  "output": 25.0, "cache_write": 6.25,  "cache_read": 0.50},
    "sonnet-4-5": {"input": 3.0,  "output": 15.0, "cache_write": 3.75,  "cache_read": 0.30},
    "haiku-4-5":  {"input": 1.0,  "output": 5.0,  "cache_write": 1.25,  "cache_read": 0.10},
    "opus":   {"input": 15.0, "output": 75.0, "cache_write": 18.75, "cache_read": 1.50},
    "sonnet": {"input": 3.0,  "output": 15.0, "cache_write": 3.75,  "cache_read": 0.30},
    "haiku":  {"input": 0.25, "output": 1.25, "cache_write": 0.30,  "cache_read": 0.03},
}


def calc_cost(model_key, inp, out, cache_read, cache_create):
    """Calculate cost in USD for token usage."""
    p = PRICING.get(model_key, PRICING["sonnet"])
    return (
        (inp / 1_000_000) * p["input"] +
        (out / 1_000_000) * p["output"] +
        (cache_read / 1_000_000) * p["cache_read"] +
        (cache_create / 1_000_000) * p["cache_write"]
    )


def calc_cache_savings(model_key, cache_read):
    """Calculate $ saved by cache hits vs input pricing."""
    p = PRICING.get(model_key, PRICING["sonnet"])
    return (cache_read / 1_000_000) * (p["input"] - p["cache_read"])


def get_model_key(model_name):
    """Extract model key for pricing lookup from full model name."""
    name = model_name.lower()
    is_4_5 = "4-5" in name or "4.5" in name
    if "opus" in name:
        return "opus-4-5" if is_4_5 else "opus"
    if "haiku" in name:
        return "haiku-4-5" if is_4_5 else "haiku"
    return "sonnet-4-5" if is_4_5 else "sonnet"


class Layout:
    """Layout configuration using anchor points."""
    def __init__(self, w):
        self.w = min(w, 200)
        self.content_w = self.w - 4

        if w >= 86:
            self.A2 = 2
            self.A3 = 4
        elif w >= 80:
            self.A2 = 1
            self.A3 = 3
        else:
            self.A2 = 0
            self.A3 = 0

        self.A1 = 0
        self.A6 = self.content_w


# ============================================================================
# UNIT TESTS
# ============================================================================

class TestFormatters(unittest.TestCase):
    """Test fixed-width formatters for alignment correctness."""

    def test_fmt_tok_fixed_width_ttok(self):
        """Verify Ttok formatting produces exact width."""
        cases = [
            (1_500_000_000_000, "  1.5 Ttok"),
            (15_000_000_000_000, " 15.0 Ttok"),
        ]
        for tokens, expected in cases:
            result = fmt_tok_fixed(tokens, 10)
            self.assertEqual(len(result), 10, f"Width mismatch for {tokens}: '{result}'")
            self.assertEqual(result, expected, f"Format mismatch for {tokens}")

    def test_fmt_tok_fixed_width_gtok(self):
        """Verify Gtok formatting produces exact width."""
        cases = [
            (1_500_000_000, "  1.5 Gtok"),
            (15_000_000_000, " 15.0 Gtok"),
        ]
        for tokens, expected in cases:
            result = fmt_tok_fixed(tokens, 10)
            self.assertEqual(len(result), 10, f"Width mismatch for {tokens}: '{result}'")
            self.assertEqual(result, expected, f"Format mismatch for {tokens}")

    def test_fmt_tok_fixed_width_mtok(self):
        """Verify Mtok formatting produces exact width."""
        cases = [
            (309_500_000, "309.5 Mtok"),
            (15_500_000, " 15.5 Mtok"),
            (1_000_000, "  1.0 Mtok"),
        ]
        for tokens, expected in cases:
            result = fmt_tok_fixed(tokens, 10)
            self.assertEqual(len(result), 10, f"Width mismatch for {tokens}: '{result}'")
            self.assertEqual(result, expected, f"Format mismatch for {tokens}")

    def test_fmt_tok_fixed_width_ktok(self):
        """Verify Ktok formatting produces exact width (all values < 1M use Ktok)."""
        cases = [
            (89_000, " 89.0 Ktok"),
            (625_000, "625.0 Ktok"),
            (1_000, "  1.0 Ktok"),
            (500, "  0.5 Ktok"),
            (1, "  0.0 Ktok"),  # Very small values round to 0.0
        ]
        for tokens, expected in cases:
            result = fmt_tok_fixed(tokens, 10)
            self.assertEqual(len(result), 10, f"Width mismatch for {tokens}: '{result}'")
            self.assertEqual(result, expected, f"Format mismatch for {tokens}")

    def test_fmt_cost_fixed_width(self):
        """Verify cost formatting produces exact width."""
        cases = [
            (464.22, "464.22 USD"),
            (1.33, "  1.33 USD"),
            (0.01, "  0.01 USD"),
            (99.99, " 99.99 USD"),
        ]
        for cost, expected in cases:
            result = fmt_cost_fixed(cost, 10)
            self.assertEqual(len(result), 10, f"Width mismatch for {cost}: '{result}'")
            self.assertEqual(result, expected, f"Format mismatch for {cost}")

    def test_fmt_usd_large(self):
        """Verify USD formatting with commas for large amounts."""
        self.assertEqual(fmt_usd(1234.56), "1,234.56 USD")
        self.assertEqual(fmt_usd(9999.99), "9,999.99 USD")

    def test_fmt_usd_small(self):
        """Verify USD formatting without commas for small amounts."""
        self.assertEqual(fmt_usd(123.45), "123.45 USD")
        self.assertEqual(fmt_usd(0.01), "0.01 USD")


class TestCalculations(unittest.TestCase):
    """Test cost calculation functions."""

    def test_calc_cost_opus_input(self):
        """Verify Opus 4.5 input pricing: 1M tokens @ $5/Mtok = $5.00"""
        cost = calc_cost("opus-4-5", 1_000_000, 0, 0, 0)
        self.assertAlmostEqual(cost, 5.0, places=2)

    def test_calc_cost_opus_output(self):
        """Verify Opus 4.5 output pricing: 1M tokens @ $25/Mtok = $25.00"""
        cost = calc_cost("opus-4-5", 0, 1_000_000, 0, 0)
        self.assertAlmostEqual(cost, 25.0, places=2)

    def test_calc_cost_opus_cache_read(self):
        """Verify Opus 4.5 cache read pricing: 1M tokens @ $0.50/Mtok = $0.50"""
        cost = calc_cost("opus-4-5", 0, 0, 1_000_000, 0)
        self.assertAlmostEqual(cost, 0.5, places=2)

    def test_calc_cost_opus_cache_write(self):
        """Verify Opus 4.5 cache write pricing: 1M tokens @ $6.25/Mtok = $6.25"""
        cost = calc_cost("opus-4-5", 0, 0, 0, 1_000_000)
        self.assertAlmostEqual(cost, 6.25, places=2)

    def test_calc_cost_sonnet(self):
        """Verify Sonnet 4.5 pricing."""
        cost = calc_cost("sonnet-4-5", 1_000_000, 1_000_000, 0, 0)
        self.assertAlmostEqual(cost, 3.0 + 15.0, places=2)  # $3 in + $15 out

    def test_calc_cache_savings_opus(self):
        """Verify cache savings: 1M reads saves $5.00 - $0.50 = $4.50"""
        savings = calc_cache_savings("opus-4-5", 1_000_000)
        self.assertAlmostEqual(savings, 4.5, places=2)

    def test_calc_cache_savings_sonnet(self):
        """Verify Sonnet cache savings: 1M reads saves $3.00 - $0.30 = $2.70"""
        savings = calc_cache_savings("sonnet-4-5", 1_000_000)
        self.assertAlmostEqual(savings, 2.7, places=2)


class TestModelKey(unittest.TestCase):
    """Test model name parsing."""

    def test_opus_4_5(self):
        self.assertEqual(get_model_key("claude-opus-4-5-20251101"), "opus-4-5")

    def test_sonnet_4_5(self):
        self.assertEqual(get_model_key("claude-sonnet-4-5-20250514"), "sonnet-4-5")

    def test_haiku_4_5(self):
        self.assertEqual(get_model_key("claude-haiku-4-5-20250101"), "haiku-4-5")

    def test_legacy_opus(self):
        self.assertEqual(get_model_key("claude-3-opus-20240229"), "opus")

    def test_legacy_sonnet(self):
        self.assertEqual(get_model_key("claude-3-sonnet-20240229"), "sonnet")

    def test_fallback_to_sonnet(self):
        self.assertEqual(get_model_key("unknown-model"), "sonnet")


class TestLayout(unittest.TestCase):
    """Test Layout class calculations."""

    def test_layout_wide(self):
        """Verify wide mode (W>=86) indentation."""
        layout = Layout(86)
        self.assertEqual(layout.A2, 2)
        self.assertEqual(layout.A3, 4)

    def test_layout_comfortable(self):
        """Verify comfortable mode (80<=W<86) indentation."""
        layout = Layout(80)
        self.assertEqual(layout.A2, 1)
        self.assertEqual(layout.A3, 3)

    def test_layout_narrow(self):
        """Verify narrow mode (W<80) indentation."""
        layout = Layout(70)
        self.assertEqual(layout.A2, 0)
        self.assertEqual(layout.A3, 0)

    def test_layout_minimum(self):
        """Verify minimum width (W=69) indentation."""
        layout = Layout(69)
        self.assertEqual(layout.A2, 0)
        self.assertEqual(layout.A3, 0)

    def test_layout_caps_at_200(self):
        """Verify width is capped at 200."""
        layout = Layout(300)
        self.assertEqual(layout.w, 200)


# ============================================================================
# INTEGRATION TESTS (via subprocess)
# ============================================================================

class TestIntegration(unittest.TestCase):
    """Integration tests using subprocess."""

    def run_tool(self, *args, width=80):
        """Run claude-usage with given args and width."""
        env = os.environ.copy()
        env['COLUMNS'] = str(width)
        result = subprocess.run(
            [str(TOOL)] + list(args),
            capture_output=True,
            text=True,
            env=env,
            timeout=10
        )
        return result

    def strip_ansi(self, text):
        """Remove ANSI escape codes."""
        return re.sub(r'\x1b\[[0-9;]*m', '', text)

    def test_default_runs(self):
        """Verify default command runs without error."""
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, f"Error: {result.stderr}")

    def test_hourly_runs(self):
        """Verify hourly command runs without error."""
        result = self.run_tool("hourly")
        self.assertEqual(result.returncode, 0, f"Error: {result.stderr}")

    def test_daily_runs(self):
        """Verify daily command runs without error."""
        result = self.run_tool("daily")
        self.assertEqual(result.returncode, 0, f"Error: {result.stderr}")

    def test_output_has_borders(self):
        """Verify output contains box borders."""
        result = self.run_tool()
        output = self.strip_ansi(result.stdout)
        self.assertIn('╭', output)
        self.assertIn('╰', output)
        self.assertIn('│', output)

    def test_narrow_width_no_overflow(self):
        """Verify no line exceeds width at W=69."""
        result = self.run_tool(width=69)
        output = self.strip_ansi(result.stdout)
        for i, line in enumerate(output.split('\n')):
            self.assertLessEqual(
                len(line), 69,
                f"Line {i+1} overflows (len={len(line)}): {line}"
            )

    def test_wide_width_no_overflow(self):
        """Verify no line exceeds width at W=86."""
        result = self.run_tool(width=86)
        output = self.strip_ansi(result.stdout)
        for i, line in enumerate(output.split('\n')):
            self.assertLessEqual(
                len(line), 86,
                f"Line {i+1} overflows (len={len(line)}): {line}"
            )

    def test_help_shows_usage(self):
        """Verify help command shows usage info."""
        result = self.run_tool("help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("claude-usage", result.stdout.lower())


if __name__ == '__main__':
    unittest.main(verbosity=2)
