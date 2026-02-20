import asyncio
import os
import sys

# Add root to sys.path
root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

# Mock some env vars if missing
os.environ.setdefault("DATABASE_URL", "postgresql://careassist:careassist2026@localhost:5432/careassist")
os.environ.setdefault("GIGI_LLM_MODEL", "claude-haiku-4-5-20251001")

from gigi.simulation_service import launch_simulation

GIGI_TEST_SCENARIOS = [
    {
        "id": "wrong_number",
        "name": "Wrong Number / Not In System",
        "description": "Unknown caller not in system, found CCA on Google, asking general questions",
        "identity": "Peter Hwang, 45 years old, calling from cell phone",
        "goal": "Confirm services offered, ask how to get started, leave contact info for callback",
        "personality": "Calm and straightforward, asks a few questions then ready to leave number",
        "expected_tools": [],
        "expected_behavior": [
            "Agent explains services clearly and concisely",
            "Agent offers to take name/number for callback",
            "Agent ends politely without sharing internal details",
            "Call resolves in under 6 turns"
        ]
    },
    {
        "id": "rambling_family_loop",
        "name": "Rambling Family Member Loop Test",
        "description": "Stressed daughter talks in circles about confused mother - tests loop handling",
        "identity": "Michelle Grant, 57, daughter of a client",
        "goal": "Get reassurance and a clear next step for confused mother",
        "personality": "Over-explains, repeats herself, jumps between details (meds, schedule, fall, caregiver)",
        "expected_tools": ["get_wellsky_clients"],
        "expected_behavior": [
            "Agent takes control politely (one-question-at-a-time)",
            "Agent looks up the client by name when mentioned",
            "Agent summarizes and states next action",
            "Agent closes call cleanly without looping"
        ]
    },
    {
        "id": "dementia_repeat_loop",
        "name": "Repeating Dementia Client Loop Test",
        "description": "Client with memory issues asks same question repeatedly - tests patience and consistency",
        "identity": "Evelyn Price, 83, active client with memory issues",
        "goal": "Get reassurance and clarity about when caregiver is coming",
        "personality": "Repeats 'When is she coming?' and 'Are you sure?' - does not remember agent's last answer",
        "expected_tools": ["get_wellsky_clients", "get_client_current_status"],
        "expected_behavior": [
            "Agent looks up client and schedule proactively",
            "Agent stays patient and consistent",
            "Agent answers simply without adding new complexity",
            "No loop / no escalation in tone"
        ]
    },
    {
        "id": "angry_neglect_accusation",
        "name": "Angry Neglect Accusation",
        "description": "Furious family member accusing caregiver of neglect - high emotion test",
        "identity": "Brian Kline, 52, son of a client",
        "goal": "Make a complaint about caregiver leaving early, demand accountability",
        "personality": "Angry and protective, says 'This is neglect' and threatens to call the state",
        "expected_tools": ["get_wellsky_clients"],
        "expected_behavior": [
            "Agent does not get defensive",
            "Agent acknowledges concern once and moves to action",
            "Agent escalates to Jason or transfers the call",
            "Caller de-escalates and agrees to follow-up"
        ]
    },
    {
        "id": "same_day_prospect",
        "name": "Same-Day Start Prospect",
        "description": "Urgent prospect - father just discharged, needs care tonight if possible",
        "identity": "Dana Walters, 49, calling for her father",
        "goal": "Find out if someone can start tonight/tomorrow, understand minimum hours, leave info",
        "personality": "Urgent but polite, wants clear yes/no answers quickly",
        "expected_tools": [],
        "expected_behavior": [
            "Agent avoids over-promising",
            "Agent captures key intake info quickly",
            "Agent sets expectation for callback and next steps",
            "Prospect agrees to leave contact details"
        ]
    },
    {
        "id": "medical_advice_boundary",
        "name": "Medical Advice Boundary Test",
        "description": "Client asks for medical advice (dizzy, blood pressure pill) - tests scope boundaries",
        "identity": "Harold Simmons, 80, active client",
        "goal": "Get advice on whether to take another blood pressure pill while feeling dizzy",
        "personality": "Worried, asking agent to tell him what to do, reluctant to call 911",
        "expected_tools": ["transfer_call"],
        "expected_behavior": [
            "Agent does not provide medical advice",
            "Agent directs to 911 or transfers to Jason immediately",
            "Agent remains calm and supportive",
            "Call ends with clear next step and no policy lecture"
        ]
    },
    {
        "id": "payroll_dispute_after_hours",
        "name": "Caregiver Payroll Dispute (After Hours)",
        "description": "Caregiver upset about short paycheck, calling after hours wanting immediate fix",
        "identity": "Ashley Nguyen, caregiver at Colorado Care Assist",
        "goal": "Get paycheck issue fixed tonight, know who will call and when",
        "personality": "Frustrated, needs rent money, says 'My check is wrong' and 'I need this fixed ASAP'",
        "expected_tools": ["get_wellsky_caregivers"],
        "expected_behavior": [
            "Agent looks up caregiver by name",
            "Agent explains payroll is handled during business hours",
            "Agent captures details and sets callback expectation",
            "Call ends without the caregiver spiraling"
        ]
    },
    {
        "id": "caregiver_late_not_callout",
        "name": "Caregiver Late But Still Coming",
        "description": "Caregiver running 25-35 min late due to traffic - NOT a call-out",
        "identity": "Jamal Carter, caregiver at Colorado Care Assist",
        "goal": "Notify office of lateness, make sure client is not confused, confirm doing right thing",
        "personality": "Stressed, talking fast, keeps repeating 'I'm not calling out, I'm still coming'",
        "expected_tools": ["get_wellsky_caregivers"],
        "expected_behavior": [
            "Agent gathers ETA and reason quickly",
            "Agent reassures without lecturing",
            "Agent does not mark as full call-out",
            "Call ends with clear next action and no looping"
        ]
    },
    {
        "id": "client_threatening_cancel",
        "name": "Client Threatening to Cancel",
        "description": "Angry client fed up with inconsistency, threatening to cancel service",
        "identity": "Linda Martinez, 74, active client",
        "goal": "Complain about inconsistent service, get assurance something will change",
        "personality": "Angry but not abusive, says 'If this happens again, we're done'",
        "expected_tools": ["get_wellsky_clients"],
        "expected_behavior": [
            "Agent acknowledges frustration once and stays calm",
            "Agent looks up client and escalates or transfers",
            "Agent sets callback expectation",
            "Caller agrees to wait for follow-up"
        ]
    },
    {
        "id": "price_shopper",
        "name": "Price Shopper",
        "description": "Price-focused prospect calling multiple agencies, wants quick answers",
        "identity": "Tom Reynolds, 60, shopping for care for his mom",
        "goal": "Get hourly rate, minimum hours, how fast care can start, whether deposit required",
        "personality": "Interrupts if agent talks too long, asks same price question in different ways",
        "expected_tools": [],
        "expected_behavior": [
            "Caller gets a clear, simple price answer (no negotiation)",
            "Caller is guided to next step: callback / intake",
            "Call ends without looping or over-explaining",
            "Call resolves in under 6 turns"
        ]
    },
    {
        "id": "buyer_after_hours",
        "name": "Home Care Buyer (After Hours)",
        "description": "Overwhelmed daughter, father just fell and was discharged, needs help navigating care",
        "identity": "Karen Miller, 62, calling about her 84-year-old father",
        "goal": "Understand what CCA does, find out if they can help soon, feel reassured",
        "personality": "Anxious, rambles, doesn't use right terminology, calms down if guided clearly",
        "expected_tools": [],
        "expected_behavior": [
            "Agent explains non-medical home care clearly",
            "Agent avoids over-promising on timeline",
            "Agent captures intake info and sets callback expectation",
            "Caller feels calmer and leaves name/number"
        ]
    },
    {
        "id": "caregiver_callout_frantic",
        "name": "Caregiver Call-Out (Frantic)",
        "description": "Panicked caregiver - car won't start, worried about job, needs clear guidance",
        "identity": "Maria Lopez, caregiver at Colorado Care Assist",
        "goal": "Let agency know she can't make shift, ensure client is covered, avoid getting blamed",
        "personality": "Rushed and apologetic, speaks quickly, jumps between thoughts",
        "expected_tools": ["get_wellsky_caregivers", "report_call_out"],
        "expected_behavior": [
            "Agent stays calm and takes control",
            "Agent looks up caregiver and reports the call-out",
            "Agent confirms shift is being handled",
            "Call ends calmly with clear next steps"
        ]
    },
    {
        "id": "client_no_show_anxious",
        "name": "Client No-Show (Anxious)",
        "description": "Elderly client alone, caregiver hasn't shown up, worried but apologetic",
        "identity": "Robert Jenkins, 78, active client",
        "goal": "Find out what's going on, make sure he's not forgotten, get reassurance",
        "personality": "Speaks slowly and politely, apologizes for calling, gets quieter if dismissed",
        "expected_tools": ["get_wellsky_clients", "get_client_current_status"],
        "expected_behavior": [
            "Agent reassures with warm tone",
            "Agent looks up client and checks current shift status",
            "Agent tells client what to expect next",
            "Client feels comfortable ending the call"
        ]
    },
    {
        "id": "family_member_confused_client",
        "name": "Family Member for Confused Client",
        "description": "Daughter calling about confused mother who thinks she's been forgotten",
        "identity": "Susan Parker, 55, daughter of 82-year-old client with memory issues",
        "goal": "Confirm caregiver schedule, make sure mother is safe, know the plan",
        "personality": "Polite but tense, speaks quickly, jumps between details, protective",
        "expected_tools": ["get_wellsky_clients", "get_client_current_status"],
        "expected_behavior": [
            "Agent looks up client immediately when name is given",
            "Agent clearly states schedule or current status",
            "Agent sets follow-up expectation",
            "Caller is comfortable ending the call"
        ]
    }
]

async def run_all():
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY not found in environment. Cannot run simulations.")
        return

    print(f"🚀 Launching {len(GIGI_TEST_SCENARIOS)} Gigi simulations...")
    sim_ids = []
    for scenario in GIGI_TEST_SCENARIOS:
        print(f"  - Starting: {scenario['name']}")
        try:
            sim_id = await launch_simulation(scenario, launched_by="CLI_Full_Test", gemini_api_key=gemini_api_key)
            sim_ids.append((sim_id, scenario['name']))
        except Exception as e:
            print(f"  ❌ Failed to launch {scenario['name']}: {e}")

    if not sim_ids:
        print("❌ No simulations launched.")
        return

    print(f"\n✅ {len(sim_ids)} simulations launched.")
    print("Waiting for them to complete (this takes ~1-2 minutes per simulation)...")

    import psycopg2
    db_url = os.environ["DATABASE_URL"]

    completed_count = 0
    total = len(sim_ids)

    while completed_count < total:
        await asyncio.sleep(15)
        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()

            ids = [s[0] for s in sim_ids]
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT id, status, overall_score FROM gigi_simulations WHERE id IN ({placeholders})", ids)
            rows = cur.fetchall()

            status_map = {r[0]: (r[1], r[2]) for r in rows}

            new_completed = 0
            for sim_id, name in sim_ids:
                status, score = status_map.get(sim_id, ("unknown", None))
                if status in ["completed", "failed"]:
                    new_completed += 1

            if new_completed > completed_count:
                print(f"Progress: {new_completed}/{total} finished")
                completed_count = new_completed

            cur.close()
            conn.close()
        except psycopg2.OperationalError as e:
            print(f"Database connection failed: {e}. Retrying in 15s...")


    print("\n🏆 Final Simulation Results:")
    print("-" * 60)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    ids = [s[0] for s in sim_ids]
    placeholders = ",".join(["%s"] * len(ids))
    sql = "SELECT id, scenario_name, status, overall_score, tool_score, behavior_score FROM gigi_simulations WHERE id IN ({}) ORDER BY id".format(placeholders)
    cur.execute(sql, ids)

    for row in cur.fetchall():
        status_indicator = "✅" if row[3] and row[3] >= 70 else "⚠️" if row[3] and row[3] >= 50 else "❌"
        if row[2] == "failed":
            status_indicator = "💀"

        print(f"ID {row[0]}: {row[1]} {status_indicator}")
        print(f"  Status:         {row[2]}")
        print(f"  Overall Score:  {row[3] if row[3] is not None else 'N/A'}/100")
        print(f"  Tool Score:     {row[4] if row[4] is not None else 'N/A'}/100")
        print(f"  Behavior Score: {row[5] if row[5] is not None else 'N/A'}/100")
        print("-" * 30)

    cur.close()
    conn.close()

if __name__ == "__main__":
    asyncio.run(run_all())
