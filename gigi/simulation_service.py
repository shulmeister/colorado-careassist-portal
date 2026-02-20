"""
Voice Brain Simulation Service

Orchestrates automated testing of the Voice Brain custom-llm agent by:
1. Simulating realistic user conversations via WebSocket
2. Capturing tool calls in real-time
3. Evaluating conversation quality against expected behaviors

Author: Colorado Care Assist
Date: February 6, 2026
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import psycopg2
import websockets

# Gemini SDK (new style)
try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state for tracking simulation tool calls
SIMULATION_TOOL_CALLS: Dict[str, List[Dict]] = {}
ACTIVE_SIMULATIONS: Dict[str, 'SimulationRunner'] = {}


def capture_simulation_tool_call(call_id: str, tool_name: str, tool_input: dict, result: str):
    """
    Called by voice_brain.py to capture tool executions during simulations.
    Only captures for call_ids starting with "sim_"
    """
    if not call_id.startswith("sim_"):
        return

    if call_id not in SIMULATION_TOOL_CALLS:
        SIMULATION_TOOL_CALLS[call_id] = []

    SIMULATION_TOOL_CALLS[call_id].append({
        "tool": tool_name,
        "input": tool_input,
        "result": result,
        "timestamp": datetime.now().isoformat()
    })

    logger.info(f"[Simulation {call_id}] Captured tool: {tool_name}")


class SimulationRunner:
    """Manages a single simulation run"""

    def __init__(self, simulation_id: int, scenario: Dict, call_id: str, launched_by: str):
        self.simulation_id = simulation_id
        self.scenario = scenario
        self.call_id = call_id
        self.launched_by = launched_by

        self.transcript: List[Dict] = []  # {role: user/assistant, content: str}
        self.status = "pending"
        self.error = None
        self.started_at = None

        # Configure Gemini (new SDK)
        if not GENAI_AVAILABLE:
            raise ValueError("google.genai SDK not installed — cannot run simulations")
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set")

        self.llm = genai.Client(api_key=gemini_api_key)
        self.llm_model = os.getenv("GIGI_LLM_MODEL", "gemini-3-flash-preview")

        # Voice Brain WebSocket URL — use current server's port
        ws_port = os.getenv("PORT", "8765")
        self.ws_url = f"ws://localhost:{ws_port}/llm-websocket/{call_id}"

        logger.info(f"[Sim {call_id}] Initialized for scenario: {scenario['name']} -> {self.ws_url}")

    async def run(self):
        """Execute the simulation"""
        try:
            self.status = "running"
            self.started_at = datetime.now()
            await self._update_db_status("running", started_at=self.started_at)

            logger.info(f"[Sim {self.call_id}] Starting simulation")

            # Initialize tool tracking
            SIMULATION_TOOL_CALLS[self.call_id] = []

            # Connect to Voice Brain
            try:
                async with websockets.connect(self.ws_url, open_timeout=10) as websocket:
                    logger.info(f"[Sim {self.call_id}] Connected to Voice Brain")

                    # Handle config + send call_details + receive greeting
                    await self._handle_initial_exchange(websocket)

                    # Run conversation for up to 10 turns or until completion
                    max_turns = 10
                    for turn in range(max_turns):
                        logger.info(f"[Sim {self.call_id}] Turn {turn + 1}/{max_turns}")

                        # Generate user response
                        user_message = await self._generate_user_response()
                        if not user_message or any(end_phrase in user_message.lower() for end_phrase in ["goodbye", "thanks, bye", "that's all", "thank you, bye"]):
                            logger.info(f"[Sim {self.call_id}] User ended conversation")
                            break

                        # Send to Voice Brain
                        await self._send_user_message(websocket, user_message)
                        self.transcript.append({"role": "user", "content": user_message})

                        # Receive response (may include ping/pong frames to skip)
                        assistant_response = await self._receive_response(websocket)
                        if assistant_response:
                            self.transcript.append({"role": "assistant", "content": assistant_response})

                            # Check for transfer (ends simulation)
                            if "transfer" in assistant_response.lower():
                                logger.info(f"[Sim {self.call_id}] Call transferred, ending")
                                break
                        else:
                            logger.warning(f"[Sim {self.call_id}] No response received")
                            break

                    # Simulation complete
                    await self._complete_simulation()

            except asyncio.TimeoutError:
                logger.error(f"[Sim {self.call_id}] WebSocket connection timeout")
                self.status = "failed"
                self.error = "Connection timeout"
                await self._update_db_status("failed", error_message="WebSocket connection timeout")

            except websockets.exceptions.WebSocketException as e:
                logger.error(f"[Sim {self.call_id}] WebSocket error: {e}")
                self.status = "failed"
                self.error = f"WebSocket error: {str(e)}"
                await self._update_db_status("failed", error_message=str(e))

        except Exception as e:
            logger.error(f"[Sim {self.call_id}] Unexpected error: {e}", exc_info=True)
            self.status = "failed"
            self.error = str(e)
            await self._update_db_status("failed", error_message=str(e))

    async def _generate_user_response(self) -> str:
        """Use Gemini to generate realistic user response"""
        prompt = f"""You are simulating a phone call to a home care agency.

Identity: {self.scenario['identity']}
Goal: {self.scenario['goal']}
Personality: {self.scenario['personality']}

IMPORTANT:
- Respond naturally as this person would in a phone conversation
- Keep responses short (1-3 sentences) like real speech
- Follow the goal but don't be robotic
- Show the personality traits
- If you've achieved your goal and the agent answered your questions, say goodbye

Conversation so far:
{self._format_transcript_for_context()}

Generate your next response as the caller (JUST the response, no meta-commentary):"""

        try:
            config = genai_types.GenerateContentConfig(
                max_output_tokens=100,
                temperature=0.7,
            )
            response = await asyncio.to_thread(
                self.llm.models.generate_content,
                model=self.llm_model,
                contents=prompt,
                config=config,
            )

            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        return part.text.strip()

            return "I understand. Can you tell me more?"

        except Exception as e:
            logger.error(f"[Sim {self.call_id}] Gemini error: {e}")
            fallback_responses = [
                "I understand. Can you tell me more?",
                "Yes, that makes sense.",
                "Okay, I see.",
            ]
            return fallback_responses[len(self.transcript) % len(fallback_responses)]

    async def _handle_initial_exchange(self, websocket):
        """Handle config + send call_details + receive greeting (Retell protocol)"""
        try:
            # 1. Receive config from voice brain
            msg = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(msg)

            if data.get("response_type") == "config":
                logger.info(f"[Sim {self.call_id}] Received config")

            # 2. Send call_details (simulating what Retell sends to trigger greeting)
            from_number = self.scenario.get("from_number", "+13074598220")
            await websocket.send(json.dumps({
                "interaction_type": "call_details",
                "call": {
                    "call_id": self.call_id,
                    "from_number": from_number,
                    "to_number": "+17208176600",
                    "direction": "inbound",
                    "call_type": "phone_call",
                    "metadata": {"simulation": True}
                }
            }))
            logger.info(f"[Sim {self.call_id}] Sent call_details (from: {from_number})")

            # 3. Receive greeting from voice brain
            msg = await asyncio.wait_for(websocket.recv(), timeout=20)
            data = json.loads(msg)

            if data.get("response_type") == "response":
                greeting = data.get("content", "")
                self.transcript.append({"role": "assistant", "content": greeting})
                logger.info(f"[Sim {self.call_id}] Greeting: {greeting[:100]}...")
            else:
                logger.warning(f"[Sim {self.call_id}] Unexpected message type after call_details: {data.get('response_type')}")

        except asyncio.TimeoutError:
            logger.error(f"[Sim {self.call_id}] Timeout waiting for initial exchange")
            raise
        except Exception as e:
            logger.error(f"[Sim {self.call_id}] Error in initial exchange: {e}")
            raise

    async def _send_user_message(self, websocket, message: str):
        """Send user message to Voice Brain (Retell protocol)"""
        payload = {
            "interaction_type": "response_required",
            "response_id": len(self.transcript),
            "transcript": self.transcript + [{"role": "user", "content": message}]
        }
        await websocket.send(json.dumps(payload))
        logger.info(f"[Sim {self.call_id}] Sent: {message[:100]}...")

    async def _receive_response(self, websocket) -> Optional[str]:
        """Receive assistant response from Voice Brain, skipping ping/pong frames"""
        deadline = asyncio.get_event_loop().time() + 45  # 45s total timeout
        try:
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                msg = await asyncio.wait_for(websocket.recv(), timeout=max(remaining, 1))
                data = json.loads(msg)

                if data.get("response_type") == "ping_pong":
                    # Voice brain might send ping/pong — respond and continue
                    await websocket.send(json.dumps({
                        "interaction_type": "ping_pong",
                        "timestamp": data.get("timestamp")
                    }))
                    continue

                if data.get("response_type") == "response":
                    content = data.get("content", "")
                    logger.info(f"[Sim {self.call_id}] Received: {content[:100]}...")
                    return content

                # tool_call_invocation / tool_call_result — skip, wait for final response
                if data.get("response_type") in ("tool_call_invocation", "tool_call_result"):
                    logger.info(f"[Sim {self.call_id}] Tool event: {data.get('response_type')}")
                    continue

                logger.info(f"[Sim {self.call_id}] Skipping message type: {data.get('response_type')}")

            logger.error(f"[Sim {self.call_id}] Timeout waiting for response")
            return None

        except asyncio.TimeoutError:
            logger.error(f"[Sim {self.call_id}] Timeout waiting for response")
            return None
        except Exception as e:
            logger.error(f"[Sim {self.call_id}] Error receiving response: {e}")
            return None

    async def _complete_simulation(self):
        """Evaluate and save results"""
        duration = (datetime.now() - self.started_at).seconds if self.started_at else 0

        # Get tool calls
        tool_calls = SIMULATION_TOOL_CALLS.get(self.call_id, [])
        tools_used = list(set([t["tool"] for t in tool_calls]))

        logger.info(f"[Sim {self.call_id}] Completing simulation - {len(self.transcript)} turns, {len(tool_calls)} tool calls")

        # Evaluate
        from gigi.simulation_evaluator import evaluate_simulation
        evaluation = await evaluate_simulation(
            scenario=self.scenario,
            transcript=self.transcript,
            tool_calls=tool_calls,
            tools_used=tools_used
        )

        # Update database
        db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
        conn = psycopg2.connect(db_url)
        try:
            cur = conn.cursor()

            cur.execute("""
                UPDATE gigi_simulations
                SET status = 'completed',
                    completed_at = %s,
                    duration_seconds = %s,
                    transcript = %s,
                    transcript_json = %s,
                    turn_count = %s,
                    tool_calls_json = %s,
                    tools_used = %s,
                    tool_score = %s,
                    behavior_score = %s,
                    overall_score = %s,
                    evaluation_details = %s
                WHERE id = %s
            """, (
                datetime.now(),
                duration,
                self._format_transcript_text(),
                json.dumps(self.transcript),
                len(self.transcript) // 2,
                json.dumps(tool_calls),
                json.dumps(tools_used),
                evaluation["tool_score"],
                evaluation["behavior_score"],
                evaluation["overall_score"],
                json.dumps(evaluation["details"]),
                self.simulation_id
            ))

            conn.commit()
            cur.close()
        finally:
            conn.close()

        logger.info(f"[Sim {self.call_id}] Completed - Score: {evaluation['overall_score']}/100")

        # Cleanup
        if self.call_id in SIMULATION_TOOL_CALLS:
            del SIMULATION_TOOL_CALLS[self.call_id]
        if self.call_id in ACTIVE_SIMULATIONS:
            del ACTIVE_SIMULATIONS[self.call_id]

    def _format_transcript_text(self) -> str:
        """Format transcript as plain text"""
        lines = []
        for turn in self.transcript:
            role = "Agent" if turn["role"] == "assistant" else "Caller"
            lines.append(f"{role}: {turn['content']}")
        return "\n\n".join(lines)

    def _format_transcript_for_context(self) -> str:
        """Format last few turns for Gemini context"""
        recent = self.transcript[-4:] if len(self.transcript) > 4 else self.transcript
        lines = []
        for turn in recent:
            role = "Agent" if turn["role"] == "assistant" else "You"
            lines.append(f"{role}: {turn['content']}")
        return "\n".join(lines) if lines else "(No conversation yet)"

    async def _update_db_status(self, status: str, **kwargs):
        """Update simulation status in database using parameterized queries"""
        db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
        conn = psycopg2.connect(db_url)
        try:
            cur = conn.cursor()

            # Build parameterized SET clause
            set_parts = ["status = %s"]
            params = [status]

            # Whitelist of allowed column names to prevent SQL injection via key names
            allowed_columns = {"started_at", "completed_at", "error_message", "duration_seconds"}

            for key, value in kwargs.items():
                if key not in allowed_columns:
                    logger.warning(f"Ignoring unknown column in _update_db_status: {key}")
                    continue
                set_parts.append(f"{key} = %s")
                if isinstance(value, datetime):
                    params.append(value.isoformat())
                else:
                    params.append(value)

            params.append(self.simulation_id)
            sql = f"UPDATE gigi_simulations SET {', '.join(set_parts)} WHERE id = %s"
            cur.execute(sql, params)
            conn.commit()
            cur.close()
        finally:
            conn.close()


async def launch_simulation(scenario: Dict, launched_by: str) -> int:
    """
    Launch a new simulation (returns simulation_id immediately).
    The simulation runs asynchronously in the background.
    """
    # Generate unique call_id with sim_ prefix
    call_id = f"sim_{uuid.uuid4().hex[:16]}"

    # Create database record
    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
    conn = psycopg2.connect(db_url)
    try:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO gigi_simulations (
                scenario_id, scenario_name, call_id, status,
                expected_tools, launched_by, created_at
            ) VALUES (%s, %s, %s, 'pending', %s, %s, NOW())
            RETURNING id
        """, (
            scenario["id"],
            scenario["name"],
            call_id,
            json.dumps(scenario.get("expected_tools", [])),
            launched_by
        ))

        simulation_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
    finally:
        conn.close()

    # Launch async runner
    runner = SimulationRunner(simulation_id, scenario, call_id, launched_by)
    ACTIVE_SIMULATIONS[call_id] = runner

    # Run in background
    asyncio.create_task(runner.run())

    logger.info(f"Launched simulation {simulation_id} (call_id: {call_id})")
    return simulation_id
