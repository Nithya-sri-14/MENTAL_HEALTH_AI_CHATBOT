from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .orchestrator import score_answers, risk_from_text, recommendations


@dataclass
class AgentMessage:
    agent_name: str
    role: str
    thought: str
    action: str
    result: str


@dataclass
class MultiAgentOrchestrationResult:
    status: str
    timestamp: str
    agents_involved: list[str]
    trace: list[AgentMessage]
    final_output: dict[str, Any]


def run_clinical_multi_agent_team(patient: dict[str, Any], answers: dict[str, int], notes: str) -> MultiAgentOrchestrationResult:
    trace = []
    
    # 1. Intake Agent (Onboarding Context)
    intake_thought = f"Reviewing patient profile for {patient.get('name')}. Primary concern is {patient.get('primary_concern')}."
    intake_action = "Parse demographic data, preferred language, and clinical history."
    intake_result = f"Patient {patient.get('name')} (Age: {patient.get('age')}) is speaking {patient.get('language')}. Engagement index is {patient.get('engagement')}%."
    trace.append(AgentMessage(
        agent_name="Patient Intake Agent",
        role="Extract demographic details and context",
        thought=intake_thought,
        action=intake_action,
        result=intake_result
    ))

    # 2. Psychometric Assessment Agent
    scorecard = score_answers(answers)
    assess_thought = f"Analyzing psychometric screening answers for stress, sleep, anxiety, mood, and routine functioning."
    assess_action = f"Apply weights to answers: {answers}. Calculate total score."
    assess_result = f"Score card computed: Stress={scorecard['stress']}, Sleep={scorecard['sleep']}, Anxiety={scorecard['anxiety']}, Mood={scorecard['mood']}, Function={scorecard['function']}. Total: {scorecard['total']}/48 (Risk: {scorecard['risk_level']})."
    trace.append(AgentMessage(
        agent_name="Clinical Assessment Agent",
        role="Score psychometric indices",
        thought=assess_thought,
        action=assess_action,
        result=assess_result
    ))

    # 3. Safety Risk Analyst Agent
    risk_info = risk_from_text(notes)
    safety_thought = "Scanning clinical transcript notes for indicators of crisis, self-harm, or clinical depression."
    safety_action = f"Run keyword regex and NLP scans on notes: '{notes[:100]}...'"
    safety_result = f"NLP Risk Score: {risk_info['score']}%. Keywords hit: {risk_info['signals']}. Escalation status: {risk_info['escalate']}."
    trace.append(AgentMessage(
        agent_name="Clinical Safety Agent",
        role="Scan for crisis & self-harm risk",
        thought=safety_thought,
        action=safety_action,
        result=safety_result
    ))

    # 4. Treatment Recommendation Agent
    recs = recommendations(scorecard, risk_info, patient.get("engagement", 70), patient.get("missed_sessions", 0))
    recs_thought = "Formulating clinical recommendations based on assessment score and safety indicators."
    recs_action = "Map severity scores to intervention protocols (sleep hygiene, mindfulness, crisis referral)."
    recs_result = f"Generated {len(recs)} treatment recommendations: {recs}"
    trace.append(AgentMessage(
        agent_name="Treatment Planner Agent",
        role="Formulate evidence-based coping guidelines",
        thought=recs_thought,
        action=recs_action,
        result=recs_result
    ))

    # Final Output
    return MultiAgentOrchestrationResult(
        status="success",
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        agents_involved=["Intake Agent", "Assessment Agent", "Safety Agent", "Planner Agent"],
        trace=trace,
        final_output={
            "scorecard": scorecard,
            "text_risk": risk_info,
            "recommendations": recs,
            "escalate": risk_info["escalate"] or scorecard["risk_level"] in {"High", "Critical"}
        }
    )
