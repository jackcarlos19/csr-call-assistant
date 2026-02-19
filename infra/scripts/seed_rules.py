import asyncio

from sqlalchemy import select

from app.db import async_session
from app.models.ruleset import Rule, RuleSet


RULES_CONFIG = {
    "keyword_alert": [
        {
            "id": "competitor_mention",
            "patterns": ["CoolBreeze", "AC Pro", "One Hour", "competitor"],
            "severity": "info",
            "message": "Competitor mentioned — acknowledge and redirect to our value proposition",
        },
        {
            "id": "price_concern",
            "patterns": ["how much", "cost", "expensive", "afford", "price"],
            "severity": "info",
            "message": "Price sensitivity detected — emphasize value and financing options",
        },
        {
            "id": "emergency_urgency",
            "patterns": ["emergency", "urgent", "can't stop", "flooding", "burst", "fire"],
            "severity": "high",
            "message": "Emergency call — prioritize dispatch, ask safety questions first",
        },
        {
            "id": "upsell_opportunity",
            "patterns": ["annual plan", "membership", "protection plan", "monthly plan"],
            "severity": "info",
            "message": "Upsell in progress — ensure no prohibited pricing claims",
        },
        {
            "id": "cancellation_mention",
            "patterns": ["cancel", "cancellation", "terminate", "end my service"],
            "severity": "warning",
            "message": "Cancellation/churn signal — follow retention protocol",
        },
    ],
    "required_question": [
        {
            "id": "confirm_service_address",
            "question": "Confirm the service address",
            "satisfy_patterns": ["address", "where.*service", "location"],
        },
        {
            "id": "confirm_callback_number",
            "question": "Confirm callback phone number",
            "satisfy_patterns": ["phone.*number", "reach you", "callback", "contact.*number"],
        },
        {
            "id": "confirm_home_warranty",
            "question": "Ask about home warranty",
            "satisfy_patterns": ["home warranty", "warranty.*cover"],
        },
        {
            "id": "confirm_water_shutoff",
            "question": "Ask if customer located water shutoff valve",
            "satisfy_patterns": ["shutoff", "shut.*off.*valve", "main.*water"],
        },
        {
            "id": "confirm_pets_children",
            "question": "Confirm children or pets in home",
            "satisfy_patterns": ["children", "pets", "kids", "animals.*home"],
        },
        {
            "id": "confirm_pest_type",
            "question": "Identify pest type",
            "satisfy_patterns": ["what.*type", "what.*kind", "describe.*pest", "what.*seeing"],
        },
    ],
    "prohibited_claim": [
        {
            "id": "guarantee_same_day",
            "patterns": ["guarantee.*today", "guarantee.*same.day", "promise.*today"],
            "severity": "critical",
            "message": "⚠️ PROHIBITED: Cannot guarantee same-day service. Say 'We will do our best to schedule today' instead.",
        },
        {
            "id": "price_lock_guarantee",
            "patterns": ["guarantee.*price", "price.*won't.*go up", "lock.*rate", "promise.*price"],
            "severity": "critical",
            "message": "⚠️ PROHIBITED: Cannot guarantee future pricing. Say 'Current pricing is...' without future commitments.",
        },
    ],
}


async def seed_rules() -> None:
    async with async_session() as db:
        ruleset_stmt = select(RuleSet).where(
            RuleSet.tenant_id.is_(None),
            RuleSet.org_id.is_(None),
            RuleSet.location_id.is_(None),
            RuleSet.campaign_id.is_(None),
            RuleSet.status == "active",
        )
        ruleset = (await db.execute(ruleset_stmt)).scalar_one_or_none()
        if ruleset is None:
            ruleset = RuleSet(status="active", version=1)
            db.add(ruleset)
            await db.flush()

        existing_rules = (
            await db.execute(select(Rule).where(Rule.ruleset_id == ruleset.id))
        ).scalars().all()
        existing_rule_ids = {
            str(rule.config.get("id"))
            for rule in existing_rules
            if isinstance(rule.config, dict) and rule.config.get("id")
        }

        seeded_count = 0
        for kind, configs in RULES_CONFIG.items():
            for config in configs:
                if config["id"] in existing_rule_ids:
                    continue
                db.add(
                    Rule(
                        ruleset_id=ruleset.id,
                        kind=kind,
                        config=config,
                        enabled=True,
                    )
                )
                seeded_count += 1

        await db.commit()
        print(f"Seeded {seeded_count} rules successfully")


def main() -> None:
    asyncio.run(seed_rules())


if __name__ == "__main__":
    main()
