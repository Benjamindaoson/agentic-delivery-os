#!/usr/bin/env python3
"""
agentctl - Unified CLI for Agentic Delivery OS
Usage:
    agentctl run <query> [--session <id>]
    agentctl inspect <run_id>
    agentctl replay <run_id>
    agentctl list [runs|sessions|agents|tools]
    agentctl serve [--port 8000]
"""

import sys
import json
import click
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from runtime.l5_engine import L5Engine
from runtime.workbench.cli import WorkbenchCLI


@click.group()
def cli():
    """Agentic Delivery OS - L5 System CLI"""
    pass


@cli.command()
@click.argument('query')
@click.option('--session', default=None, help='Session ID')
@click.option('--user', default='default_user', help='User ID')
def run(query, session, user):
    """Execute a new task run"""
    engine = L5Engine()
    click.echo(f"🚀 Executing: {query}")
    
    result = engine.execute_run(query, session_id=session, user_id=user)
    
    click.echo(f"\n✅ Run ID: {result['run_id']}")
    click.echo(f"📊 Session: {result['session_id']}")
    click.echo(f"🎯 Task Type: {result['classification'].task_type}")
    click.echo(f"💯 Quality Score: {result['eval'].quality_score:.2%}")
    click.echo(f"💰 Cost: ${result['eval'].cost:.4f}")
    click.echo(f"⏱️  Latency: {result['eval'].latency:.0f}ms")
    
    click.echo(f"\n📁 Artifacts:")
    click.echo(f"  - Goal: artifacts/goals/{result['run_id']}_goal_interpretation.json")
    click.echo(f"  - Plan: artifacts/goals/{result['run_id']}_high_level_plan.json")
    click.echo(f"  - Eval: artifacts/eval/{result['run_id']}.json")


@cli.command()
@click.argument('run_id')
def inspect(run_id):
    """Inspect a completed run"""
    artifacts_base = "artifacts/goals"
    
    click.echo(f"🔍 Inspecting Run: {run_id}\n")
    
    # Load goal interpretation
    goal_path = f"{artifacts_base}/{run_id}_goal_interpretation.json"
    if os.path.exists(goal_path):
        with open(goal_path) as f:
            goal = json.load(f)
            click.echo("🎯 Goal Interpretation:")
            click.echo(f"  Primary Goal: {goal['primary_goal']}")
            click.echo(f"  Success Criteria: {', '.join(goal['success_criteria'])}")
            click.echo(f"  Confidence: {goal['confidence_score']:.2%}\n")
    
    # Load plan
    plan_path = f"{artifacts_base}/{run_id}_high_level_plan.json"
    if os.path.exists(plan_path):
        with open(plan_path) as f:
            plan = json.load(f)
            click.echo("📋 High-Level Plan:")
            click.echo(f"  Strategy: {plan['strategy_selected']}")
            click.echo(f"  Stages: {' → '.join(plan['stages'])}\n")
    
    # Load eval
    eval_path = f"artifacts/eval/{run_id}.json"
    if os.path.exists(eval_path):
        with open(eval_path) as f:
            eval_data = json.load(f)
            click.echo("📊 Evaluation:")
            click.echo(f"  Quality: {eval_data['quality_score']:.2%}")
            click.echo(f"  Success: {'✅' if eval_data['success'] else '❌'}")
            click.echo(f"  Cost: ${eval_data['cost']:.4f}")


@cli.command()
@click.argument('run_id')
def replay(run_id):
    """Replay a historical run"""
    click.echo(f"🔄 Replaying Run: {run_id}\n")
    
    # Load original task
    task_path = f"artifacts/task_type/{run_id}.json"
    if not os.path.exists(task_path):
        click.echo("❌ Run not found")
        return
    
    with open(task_path) as f:
        task = json.load(f)
    
    click.echo(f"📝 Original Task: {task['run_id']}")
    click.echo(f"🏷️  Type: {task['task_type']}")
    click.echo(f"🧠 Complexity: {task['complexity']}")
    click.echo(f"🔧 Capabilities: {', '.join(task['required_capabilities'])}")
    
    # Show execution timeline
    click.echo(f"\n⏱️  Timeline:")
    artifacts_dir = "artifacts/goals"
    for file in sorted(os.listdir(artifacts_dir)):
        if file.startswith(run_id):
            click.echo(f"  ✓ {file}")


@cli.command()
@click.argument('entity_type', type=click.Choice(['runs', 'sessions', 'agents', 'tools']))
def list(entity_type):
    """List entities"""
    if entity_type == 'runs':
        click.echo("📜 Recent Runs:\n")
        eval_dir = "artifacts/eval"
        if os.path.exists(eval_dir):
            runs = sorted(os.listdir(eval_dir), key=lambda x: os.path.getmtime(f"{eval_dir}/{x}"), reverse=True)[:10]
            for run_file in runs:
                run_id = run_file.replace('.json', '')
                with open(f"{eval_dir}/{run_file}") as f:
                    data = json.load(f)
                    status = "✅" if data['success'] else "❌"
                    click.echo(f"{status} {run_id} | Q:{data['quality_score']:.2%} | ${data['cost']:.4f}")
    
    elif entity_type == 'agents':
        click.echo("🤖 Agent Profiles:\n")
        cli_tool = WorkbenchCLI()
        cli_tool.show_agent_profiles()
    
    elif entity_type == 'sessions':
        click.echo("💬 Sessions:\n")
        sessions_dir = "artifacts/session"
        if os.path.exists(sessions_dir):
            for session_file in os.listdir(sessions_dir):
                with open(f"{sessions_dir}/{session_file}") as f:
                    data = json.load(f)
                    click.echo(f"📌 {data['session_id']} | Runs: {len(data['run_ids'])} | User: {data['user_id']}")
    
    elif entity_type == 'tools':
        click.echo("🔧 Tool Profiles:\n")
        tools_dir = "artifacts/tool_profiles"
        if os.path.exists(tools_dir):
            for tool_file in os.listdir(tools_dir):
                with open(f"{tools_dir}/{tool_file}") as f:
                    data = json.load(f)
                    enabled = "✅" if data.get('is_enabled', data.get('enabled', True)) else "❌"
                    click.echo(f"{enabled} {data['tool_id']}")


@cli.command()
@click.option('--port', default=8000, help='Port number')
def serve(port):
    """Start REST API server"""
    click.echo(f"🚀 Starting Agentic OS API on port {port}...")
    os.system(f"uvicorn api_server:app --host 0.0.0.0 --port {port}")


if __name__ == '__main__':
    cli()



