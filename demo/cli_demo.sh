#!/usr/bin/env bash
# AgentGate CLI Demo
# Demonstrates runtime secret injection via the agentgate CLI

set -e

echo "=========================================="
echo "  AgentGate CLI Demo"
echo "=========================================="
echo ""

# Step 1: Validate policies
echo "→ Step 1: Validate policies"
agentgate policy validate
echo ""

# Step 2: List loaded policies
echo "→ Step 2: List loaded policies"
agentgate policy list
echo ""

# Step 3: Run a command with injected secrets
echo "→ Step 3: Run a command with secrets injected"
echo "  Command: env | grep -i demo"
echo ""
agentgate run --task deploy --env development -- env
echo ""

# Step 4: View audit trail
echo "→ Step 4: Recent audit entries"
agentgate audit tail --limit 10
echo ""

echo "=========================================="
echo "  CLI Demo complete"
echo "=========================================="
