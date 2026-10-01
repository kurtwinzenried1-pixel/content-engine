import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engines.content.generate_social import generate as generate_social
from engines.content.generate_seo import generate as generate_seo
from engines.creative.generate_visual_briefs import generate as generate_visual_briefs
from engines.creative.render_graphics import render as render_graphics
from engines.leads.generate_leads import generate as generate_leads
from engines.reels.transcribe import transcribe_job
from engines.reels.plan_reel import plan as plan_reel
from engines.reels.render_reel_v2 import render_job


JOBS_DIR = ROOT / "core" / "jobs"
EXPORTS_DIR = ROOT / "exports"


def load_job(job_id):
    job_file = JOBS_DIR / f"{job_id}.json"

    if not job_file.exists():
        raise FileNotFoundError(
            f"Job nicht gefunden: {job_file}"
        )

    return job_file, json.loads(
        job_file.read_text(
            encoding="utf-8-sig"
        )
    )


def save_job(job_file, job):
    job_file.write_text(
        json.dumps(
            job,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def build_delivery_package(job_id, job):
    job_export_dir = EXPORTS_DIR / job_id
    package_dir = job_export_dir / "delivery"

    package_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    excluded_names = {
        "delivery-package.zip",
        "delivery-message.txt",
        "manifest.json",
    }

    delivery_files = [
        file
        for file in job_export_dir.rglob("*")
        if file.is_file()
        and file.name not in excluded_names
        and package_dir not in file.parents
    ]

    buyer = (
        job.get("fiverr_buyer")
        or "there"
    )

    order_id = (
        job.get("fiverr_order_id")
        or job_id
    )

    job_type = job.get(
        "job_type",
        "project",
    )

    message = f"""Hello {buyer},

thank you for your order.

Your {job_type.replace("_", " ")} delivery is complete.

Order reference:
{order_id}

I have included all finished files in the delivery package.

Please review the files and let me know through Fiverr if you need a revision within the scope of the order.

Best regards
Chris
"""

    message_path = (
        package_dir
        / "delivery-message.txt"
    )

    message_path.write_text(
        message,
        encoding="utf-8",
    )

    manifest = {
        "job_id": job_id,
        "fiverr_order_id": job.get(
            "fiverr_order_id"
        ),
        "buyer": job.get(
            "fiverr_buyer"
        ),
        "job_type": job_type,
        "files": [
            str(
                file.relative_to(
                    job_export_dir
                )
            ).replace("\\", "/")
            for file in delivery_files
        ],
    }

    manifest_path = (
        package_dir
        / "manifest.json"
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    zip_path = (
        package_dir
        / "delivery-package.zip"
    )

    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for file in delivery_files:
            archive.write(
                file,
                file.relative_to(
                    job_export_dir
                ),
            )

        archive.write(
            message_path,
            "delivery-message.txt",
        )

        archive.write(
            manifest_path,
            "manifest.json",
        )

    return {
        "package": str(
            zip_path.relative_to(ROOT)
        ),
        "message": message,
        "file_count": len(
            delivery_files
        ),
    }


def execute(job_id):
    job_file, job = load_job(job_id)

    job["status"] = "processing"
    job.pop("error", None)

    if job.get("source") == "fiverr":
        job["operator_status"] = "processing"
        job["delivery_status"] = "pending"
        job["requires_human_review"] = True

    save_job(job_file, job)

    try:
        job_type = job["job_type"]

        if job_type == "social_content":
            output, count = generate_social(job_id)

            result = {
                "output": str(output),
                "count": count,
            }

        elif job_type == "seo_content":
            output, article = generate_seo(job_id)

            result = {
                "output": str(output),
                "title": article["title"],
            }

        elif job_type == "graphics":
            social_output, count = generate_social(job_id)

            briefs_output, visuals = generate_visual_briefs(
                job_id
            )

            graphics_dir, files = render_graphics(
                job_id
            )

            result = {
                "social_output": str(social_output),
                "briefs_output": str(briefs_output),
                "graphics_output": str(graphics_dir),
                "count": len(files),
            }

        elif job_type == "reels":
            transcript_output, _ = transcribe_job(
                job_id
            )

            plan_output, reel = plan_reel(
                job_id
            )

            render_id, render_output = render_job(
                job_id
            )

            result = {
                "transcript": str(transcript_output),
                "plan": str(plan_output),
                "render_job": str(render_output),
                "render_id": render_id,
                "duration": reel["duration"],
            }

        elif job_type == "lead_generation":
            output, rows = generate_leads(
                job_id
            )

            result = {
                "output": str(output),
                "count": len(rows),
            }

        else:
            raise ValueError(
                f"Unsupported job_type: {job_type}"
            )

        job["status"] = "completed"
        job["result"] = result

        if job.get("source") == "fiverr":
            delivery = build_delivery_package(
                job_id,
                job,
            )

            job["delivery_package"] = (
                delivery["package"]
            )
            job["delivery_message"] = (
                delivery["message"]
            )
            job["delivery_file_count"] = (
                delivery["file_count"]
            )
            job["delivery_status"] = "ready"
            job["operator_status"] = "review_ready"
            job["requires_human_review"] = True

        save_job(job_file, job)

        return job

    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)

        if job.get("source") == "fiverr":
            job["operator_status"] = "needs_chris"
            job["requires_human_review"] = True

        save_job(job_file, job)

        raise


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("JOB_EXECUTOR_READY")
        print(
            "USAGE: python execute.py JOB-XXXXXXXX"
        )
        sys.exit(0)

    result = execute(
        sys.argv[1]
    )

    print("JOB_EXECUTION_COMPLETED")
    print(
        f"JOB_ID={result['job_id']}"
    )
    print(
        f"TYPE={result['job_type']}"
    )
    print(
        f"STATUS={result['status']}"
    )

