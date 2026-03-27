import logging

from lead_generation.engine import generate_leads
from workflows.lead_workflow import write_leads_to_sheet, run_lead_audit_workflow


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("pipeline")

_NICHE = "cafe"
_CITY = "Ahmedabad"
_AREAS = ["Satellite", "Bopal", "Prahladnagar"]
_LIMIT = 50


def main() -> None:
    logger.info("Pipeline started")

    try:
        logger.info("Starting lead generation")
        leads = generate_leads(
            niche=_NICHE,
            city=_CITY,
            areas=_AREAS,
            limit=_LIMIT,
        )
        logger.info(f"Lead generation complete. {len(leads)} leads discovered.")

    except Exception as e:
        logger.error(f"Lead generation failed: {e}")
        return

    try:
        logger.info("Writing leads to Lead Database sheet")
        write_leads_to_sheet(leads)
        logger.info("Lead Database update complete")

    except Exception as e:
        logger.error(f"Failed writing leads to sheet: {e}")
        return

    try:
        logger.info("Running website audit workflow")
        run_lead_audit_workflow()
        logger.info("Website audits completed")

    except Exception as e:
        logger.error(f"Website audit workflow failed: {e}")
        return

    logger.info("Pipeline finished successfully")


if __name__ == "__main__":
    main()