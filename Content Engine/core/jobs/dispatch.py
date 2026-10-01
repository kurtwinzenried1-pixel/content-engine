from typing import Literal


JobType = Literal[
    "social_content",
    "seo_content",
    "graphics",
    "reels",
    "lead_generation",
]


ENGINE_MODULES = {
    "social_content": "engines.content.generate_social",
    "seo_content": "engines.content.generate_seo",
    "graphics": "engines.creative.render_graphics",
    "reels": "engines.reels.render_reel",
    "lead_generation": "engines.leads.generate_leads",
}


def resolve_engine(job_type: str) -> str:
    try:
        return ENGINE_MODULES[job_type]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported job_type: {job_type}"
        ) from exc


if __name__ == "__main__":
    print("DISPATCHER_READY")

    for job_type, module in ENGINE_MODULES.items():
        print(f"{job_type} -> {module}")
