from __future__ import annotations

from flask import Blueprint, request, jsonify

from app.services import orchestrator
from app.services.validation import validate_agent_config

agents_bp = Blueprint("agents", __name__)


@agents_bp.route("/agents", methods=["POST"])
def create_agent():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    errors = validate_agent_config(data)
    if errors:
        return jsonify({"errors": errors}), 422

    agent = orchestrator.create_agent(data)
    return jsonify(agent.to_dict()), 201


@agents_bp.route("/agents", methods=["GET"])
def list_agents():
    user_id = request.args.get("userId")
    agents = orchestrator.list_agents(user_id=user_id)
    return jsonify([a.to_dict() for a in agents])


@agents_bp.route("/agents/<agent_id>", methods=["GET"])
def get_agent(agent_id: str):
    agent = orchestrator.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found."}), 404
    return jsonify(agent.to_dict())


@agents_bp.route("/agents/<agent_id>", methods=["PUT"])
def update_agent(agent_id: str):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    existing = orchestrator.get_agent(agent_id)
    if not existing:
        return jsonify({"error": "Agent not found."}), 404

    merged = existing.to_dict()
    merged.update(data)
    errors = validate_agent_config(merged)
    if errors:
        return jsonify({"errors": errors}), 422

    agent = orchestrator.update_agent(agent_id, data)
    return jsonify(agent.to_dict())


@agents_bp.route("/agents/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id: str):
    deleted = orchestrator.delete_agent(agent_id)
    if not deleted:
        return jsonify({"error": "Agent not found."}), 404
    return jsonify({"message": "Agent deleted."}), 200


@agents_bp.route("/agents/<agent_id>/assemble", methods=["POST"])
def assemble_prompt(agent_id: str):
    """Preview the fully-assembled prompt for a configured agent."""
    agent = orchestrator.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found."}), 404

    result = orchestrator.assemble_prompt(agent)
    return jsonify(result)
